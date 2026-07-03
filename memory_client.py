from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from memory_config import MemoryConfig, load_config
from memory_queue import MemoryQueue


VALID_TYPES = {"preference", "fact", "decision", "correction"}
VALID_SCOPES = {"private", "shared"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_uuid(text: str, client_name: str) -> str:
    digest = hashlib.sha256(f"{client_name}\0{text}".encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest[:32]))


class MemoryClient:
    def __init__(self, config: MemoryConfig | None = None):
        self.config = config or load_config()
        self.queue = MemoryQueue(self.config.queue_path)

    def _qdrant_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.qdrant_api_key:
            headers["api-key"] = self.config.qdrant_api_key
        return headers

    def _embed(self, text: str) -> list[float]:
        if not self.config.siliconflow_api_key:
            raise RuntimeError("Missing SILICONFLOW_API_KEY")
        headers = {
            "Authorization": f"Bearer {self.config.siliconflow_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.config.embed_model, "input": text}
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                "https://api.siliconflow.cn/v1/embeddings",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        vector = data["data"][0]["embedding"]
        if len(vector) != self.config.vector_size:
            raise RuntimeError(
                f"Embedding dimension mismatch: got {len(vector)}, expected {self.config.vector_size}"
            )
        return vector

    def ensure_collections(self) -> None:
        for collection in [self.config.collection, "memory_shared"]:
            self._ensure_collection(collection)

    def _ensure_collection(self, collection: str) -> None:
        url = f"{self.config.qdrant_url}/collections/{collection}"
        with httpx.Client(timeout=10.0, headers=self._qdrant_headers()) as client:
            response = client.get(url)
            if response.status_code == 200:
                return
            if response.status_code != 404:
                response.raise_for_status()
            create = client.put(
                url,
                json={
                    "vectors": {
                        "size": self.config.vector_size,
                        "distance": "Cosine",
                    }
                },
            )
            create.raise_for_status()

    def enqueue_write(
        self,
        text: str,
        memory_type: str = "fact",
        importance: int = 3,
        tags: list[str] | None = None,
        scope: str | None = None,
        target_id: str | None = None,
    ) -> int:
        payload = {
            "text": text,
            "type": memory_type,
            "importance": importance,
            "tags": tags or [],
            "scope": scope or self.config.default_scope,
            "target_id": target_id,
        }
        self._validate_payload(payload)
        return self.queue.enqueue("write", payload)

    def flush(self, limit: int = 20) -> tuple[int, int]:
        self.ensure_collections()
        done = 0
        failed = 0
        for item in self.queue.pending(limit=limit):
            try:
                if item.operation != "write":
                    raise RuntimeError(f"Unsupported queue operation: {item.operation}")
                self._write_now(**item.payload)
                self.queue.mark_done(item.id)
                done += 1
            except Exception as exc:
                self.queue.mark_failed(item.id, str(exc))
                failed += 1
        return done, failed

    def write(
        self,
        text: str,
        memory_type: str = "fact",
        importance: int = 3,
        tags: list[str] | None = None,
        scope: str | None = None,
        target_id: str | None = None,
    ) -> str:
        self.ensure_collections()
        return self._write_now(
            text=text,
            memory_type=memory_type,
            importance=importance,
            tags=tags or [],
            scope=scope or self.config.default_scope,
            target_id=target_id,
        )

    def _write_now(
        self,
        text: str,
        memory_type: str,
        importance: int,
        tags: list[str],
        scope: str,
        target_id: str | None = None,
    ) -> str:
        payload = {
            "text": text,
            "type": memory_type,
            "importance": importance,
            "tags": tags,
            "scope": scope,
            "target_id": target_id,
        }
        self._validate_payload(payload)
        vector = self._embed(text)
        point_id = stable_uuid(text, self.config.client_name)
        point_payload = {
            "text": text,
            "type": memory_type,
            "importance": importance,
            "tags": tags,
            "scope": scope,
            "source": self.config.client_name,
            "schema_version": "1.1",
            "client_version": "0.1.0",
            "created_at": utc_now(),
            "expiry": None,
        }
        if target_id:
            point_payload["target_id"] = target_id
        collection = "memory_shared" if scope == "shared" else self.config.collection
        with httpx.Client(timeout=10.0, headers=self._qdrant_headers()) as client:
            response = client.put(
                f"{self.config.qdrant_url}/collections/{collection}/points",
                json={
                    "points": [
                        {
                            "id": point_id,
                            "vector": vector,
                            "payload": point_payload,
                        }
                    ]
                },
            )
            response.raise_for_status()
        return point_id

    def search(
        self,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
        include_shared: bool = True,
    ) -> list[dict[str, Any]]:
        vector = self._embed(query)
        collections = [self.config.collection]
        if include_shared:
            collections.append("memory_shared")
        results: list[dict[str, Any]] = []
        for collection in collections:
            results.extend(self._search_collection(collection, vector, limit, memory_type))
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def _search_collection(
        self,
        collection: str,
        vector: list[float],
        limit: int,
        memory_type: str | None,
    ) -> list[dict[str, Any]]:
        query_filter = None
        if memory_type:
            query_filter = {
                "must": [
                    {
                        "key": "type",
                        "match": {"value": memory_type},
                    }
                ]
            }
        body: dict[str, Any] = {
            "vector": vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }
        if query_filter:
            body["filter"] = query_filter
        with httpx.Client(timeout=10.0, headers=self._qdrant_headers()) as client:
            response = client.post(
                f"{self.config.qdrant_url}/collections/{collection}/points/search",
                json=body,
            )
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
        return [
            {
                "collection": collection,
                "id": item.get("id"),
                "score": item.get("score", 0),
                "payload": item.get("payload", {}),
            }
            for item in data.get("result", [])
        ]

    def health(self) -> dict[str, str]:
        status: dict[str, str] = {}
        started = time.monotonic()
        try:
            with httpx.Client(timeout=5.0, headers=self._qdrant_headers()) as client:
                response = client.get(f"{self.config.qdrant_url}/healthz")
                response.raise_for_status()
            status["qdrant"] = "ok"
        except Exception as exc:
            status["qdrant"] = f"fail: {exc}"
        try:
            self.ensure_collections()
            status["collections"] = "ok"
        except Exception as exc:
            status["collections"] = f"fail: {exc}"
        try:
            self._embed("health check")
            status["embedding"] = "ok"
        except Exception as exc:
            status["embedding"] = f"fail: {exc}"
        status["elapsed_ms"] = str(int((time.monotonic() - started) * 1000))
        return status

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        if not payload["text"].strip():
            raise ValueError("text must not be empty")
        if payload["type"] not in VALID_TYPES:
            raise ValueError(f"type must be one of: {', '.join(sorted(VALID_TYPES))}")
        if not 1 <= int(payload["importance"]) <= 5:
            raise ValueError("importance must be between 1 and 5")
        if payload["scope"] not in VALID_SCOPES:
            raise ValueError("scope must be private or shared")
