from __future__ import annotations

import os
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from memory_client import MemoryClient
from memory_config import load_config


load_dotenv()

ClientName = Literal["claude_code", "hermes"]
MemoryType = Literal["preference", "fact", "decision", "correction"]
Scope = Literal["private", "shared"]

app = FastAPI(title="Memory Web", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("MEMORY_WEB_CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MemoryCreate(BaseModel):
    text: str = Field(min_length=1)
    client: ClientName = "claude_code"
    type: MemoryType = "fact"
    importance: int = Field(default=3, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    scope: Scope = "private"
    target_id: str | None = None
    flush: bool = True


class FlushRequest(BaseModel):
    client: ClientName = "claude_code"
    limit: int = Field(default=100, ge=1, le=1000)


def require_auth(authorization: str | None = Header(default=None)) -> None:
    token = os.getenv("MEMORY_WEB_TOKEN")
    if not token:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Missing or invalid MEMORY_WEB_TOKEN")


def client_for(client_name: ClientName) -> MemoryClient:
    return MemoryClient(load_config(client_name))


@app.get("/api/health")
def health(
    client: ClientName = Query(default="claude_code"),
    _: None = Depends(require_auth),
) -> dict[str, Any]:
    memory = client_for(client)
    return {
        "client": client,
        "collection": memory.config.collection,
        "queue": memory.queue.stats(),
        "checks": memory.health(),
    }


@app.get("/api/search")
def search(
    q: str = Query(min_length=1),
    client: ClientName = Query(default="claude_code"),
    limit: int = Query(default=8, ge=1, le=50),
    memory_type: MemoryType | None = Query(default=None),
    include_shared: bool = Query(default=True),
    _: None = Depends(require_auth),
) -> dict[str, Any]:
    memory = client_for(client)
    return {
        "items": memory.search(
            query=q,
            limit=limit,
            memory_type=memory_type,
            include_shared=include_shared,
        )
    }


@app.post("/api/memories")
def create_memory(
    body: MemoryCreate,
    _: None = Depends(require_auth),
) -> dict[str, Any]:
    memory = client_for(body.client)
    queue_id = memory.enqueue_write(
        text=body.text,
        memory_type=body.type,
        importance=body.importance,
        tags=body.tags,
        scope=body.scope,
        target_id=body.target_id,
    )
    result: dict[str, Any] = {"queued": queue_id}
    if body.flush:
        done, failed = memory.flush(limit=20)
        result["flush"] = {"done": done, "failed": failed}
    return result


@app.post("/api/flush")
def flush_queue(
    body: FlushRequest,
    _: None = Depends(require_auth),
) -> dict[str, Any]:
    memory = client_for(body.client)
    done, failed = memory.flush(limit=body.limit)
    return {"done": done, "failed": failed, "queue": memory.queue.stats()}


@app.get("/api/queue")
def queue(
    client: ClientName = Query(default="claude_code"),
    _: None = Depends(require_auth),
) -> dict[str, Any]:
    memory = client_for(client)
    return {"queue": memory.queue.stats()}


static_dir = os.getenv("MEMORY_WEB_STATIC_DIR", "/workspace/asset-management/frontend/dist")
if os.path.isdir(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str = "") -> FileResponse:
        return FileResponse(os.path.join(static_dir, "index.html"))
