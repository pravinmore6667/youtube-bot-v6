import asyncio
import json
import os
from typing import Dict, Any
from utils.logger import get_logger

log = get_logger("ChannelMemoryAgent")

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False
    log.warning("ChromaDB not found. Vector memory will be simulated using local files.")

# Initialize ChromaDB client lazily
_chroma_client = None

def get_chroma_client():
    global _chroma_client
    if not HAS_CHROMA:
        return None
    if _chroma_client is None:
        db_path = os.path.join("database", "chroma_memory")
        os.makedirs(db_path, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=db_path)
    return _chroma_client

async def save_channel_memory(data: Dict[str, Any]) -> None:
    """
    Store thumbnail styles, viral hooks, best-performing titles,
    audience preferences, retention history, and best upload timing
    in a persistent vector database (ChromaDB) for cross-video learning.
    """
    channel_id = data.get("channel_id", "default_channel")
    client = get_chroma_client()

    if client:
        collection = client.get_or_create_collection(name=f"memory_{channel_id}")

        # We store the latest aggregate state with a fixed ID
        doc_id = "latest_aggregate_memory"

        # Serialize metadata properly
        metadata = {}
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool)):
                metadata[k] = v
            else:
                metadata[k] = json.dumps(v)

        document = json.dumps(data)

        # Add or update
        collection.upsert(
            documents=[document],
            metadatas=[metadata],
            ids=[doc_id]
        )
        log.info(f"Saved real vector memory for channel: {channel_id}")
    else:
        # Fallback to local file
        mem_path = f"database/{channel_id}_memory.json"
        os.makedirs("database", exist_ok=True)
        with open(mem_path, "w") as f:
            json.dump(data, f, indent=4)
        log.info(f"Saved simulated memory for channel: {channel_id}")

async def get_channel_memory(channel_id: str) -> Dict[str, Any]:
    """
    Retrieve stored channel memory to maintain unique personality,
    editing style, and storytelling structure using ChromaDB.
    """
    client = get_chroma_client()
    default_memory = {
        "preferred_hook_style": "Curiosity gap",
        "best_upload_timing": "15:00 UTC",
        "editing_style": "Fast-paced, high energy",
        "thumbnail_style": "High contrast, neon accents",
        "audience_preferences": "Action-oriented, short sentences"
    }

    if client:
        try:
            collection = client.get_collection(name=f"memory_{channel_id}")
            result = collection.get(ids=["latest_aggregate_memory"])
            if result and result.get("documents") and len(result["documents"]) > 0:
                doc = result["documents"][0]
                memory = json.loads(doc)
                log.info(f"Retrieved real vector memory for channel: {channel_id}")
                return {**default_memory, **memory}
        except Exception as e:
            log.warning(f"Chroma collection not found or error: {e}. Returning default memory.")
    else:
        # Fallback to local file
        mem_path = f"database/{channel_id}_memory.json"
        if os.path.exists(mem_path):
            try:
                with open(mem_path, "r") as f:
                    memory = json.load(f)
                log.info(f"Retrieved simulated memory for channel: {channel_id}")
                return {**default_memory, **memory}
            except Exception:
                pass

    return default_memory
