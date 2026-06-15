import logging
from typing import List, Optional

import httpx

from app.config import settings
from app.core.runtime_config import get_model_config

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """用户提供的Embedding模型HTTP客户端"""

    def __init__(self):
        self.timeout = 60.0

    def _config(self):
        cfg = get_model_config()
        return {
            "api_url": cfg.get("EMBEDDING_API_URL") or settings.EMBEDDING_SERVICE_URL,
            "model": cfg.get("EMBEDDING_MODEL") or settings.EMBEDDING_MODEL,
            "api_key": cfg.get("EMBEDDING_API_KEY") or settings.EMBEDDING_API_KEY,
        }

    async def embed(self, text: str) -> List[float]:
        result = await self.embed_batch([text])
        return result[0] if result else []

    async def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            embeddings = await self._call_api(batch)
            all_embeddings.extend(embeddings)
        return all_embeddings

    async def _call_api(self, texts: List[str]) -> List[List[float]]:
        cfg = self._config()
        headers = {"Content-Type": "application/json"}
        if cfg["api_key"]:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"

        payload = {
            "model": cfg["model"],
            "input": texts
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(cfg["api_url"], json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                
                if "data" in data:
                    embeddings = sorted(data["data"], key=lambda x: x.get("index", 0))
                    return [item["embedding"] for item in embeddings]
                elif isinstance(data, list):
                    return data
                else:
                    logger.warning("Unknown embedding response format")
                    return []
        except Exception as e:
            logger.exception(f"Embedding API call failed: {e}")
            dim = settings.EMBEDDING_DIMENSION
            return [[0.0] * dim] * len(texts)

embedding_client = EmbeddingClient()
