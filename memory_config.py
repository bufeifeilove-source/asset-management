from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


COLLECTIONS = {
    "hermes": "memory_hermes",
    "claude_code": "memory_claude_code",
}


@dataclass(frozen=True)
class MemoryConfig:
    qdrant_url: str
    qdrant_api_key: str | None
    siliconflow_api_key: str
    embed_model: str
    vector_size: int
    client_name: str
    default_scope: str
    queue_path: Path

    @property
    def collection(self) -> str:
        return COLLECTIONS.get(self.client_name, f"memory_{self.client_name}")


def load_config(client_name: str | None = None) -> MemoryConfig:
    load_dotenv()
    selected_client = client_name or os.getenv("MEMORY_CLIENT_NAME", "claude_code")
    api_key = os.getenv("SILICONFLOW_API_KEY", "")
    queue_path = Path(
        os.getenv(
            "MEMORY_QUEUE_PATH",
            "~/.local/share/memory-system/memory_queue.sqlite3",
        )
    ).expanduser()
    return MemoryConfig(
        qdrant_url=os.getenv("MEMORY_QDRANT_URL", "http://100.81.130.84:6333").rstrip("/"),
        qdrant_api_key=os.getenv("MEMORY_QDRANT_API_KEY") or None,
        siliconflow_api_key=api_key,
        embed_model=os.getenv("MEMORY_EMBED_MODEL", "Qwen/Qwen3-Embedding-8B"),
        vector_size=int(os.getenv("MEMORY_VECTOR_SIZE", "4096")),
        client_name=selected_client,
        default_scope=os.getenv("MEMORY_DEFAULT_SCOPE", "private"),
        queue_path=queue_path,
    )
