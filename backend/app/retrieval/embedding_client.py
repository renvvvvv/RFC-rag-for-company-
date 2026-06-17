import logging
import time
from typing import List, Optional

import httpx

from app.config import settings
from app.core.runtime_config import get_model_config

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """用户提供的Embedding模型HTTP客户端"""

    def __init__(self):
        self.timeout = 60.0
        self.max_retries = 3
        self.base_delay = 1.0

    def _should_retry(self, exc: Exception) -> bool:
        """Return True for transient network/rate-limit errors."""
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            return code == 429 or code >= 500
        return isinstance(exc, (httpx.NetworkError, httpx.TimeoutException))

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
            "input": texts,
        }
        # Some OpenAI-compatible providers (e.g. OpenAI text-embedding-3) support
        # a `dimensions` parameter to down-project to a smaller vector.  Only send
        # it when it differs from the default so providers that do not support it
        # are not broken.
        dim = settings.EMBEDDING_DIMENSION
        if dim and dim not in (None, 0):
            payload["dimensions"] = dim

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        cfg["api_url"], json=payload, headers=headers
                    )
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
                last_exc = e
                if attempt < self.max_retries and self._should_retry(e):
                    delay = self.base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Embedding API attempt %s/%s failed (%s); retrying in %.1fs",
                        attempt,
                        self.max_retries,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                break

        logger.exception("Embedding API call failed after %s attempts: %s", self.max_retries, last_exc)
        dim = settings.EMBEDDING_DIMENSION
        return [[0.0] * dim] * len(texts)

embedding_client = EmbeddingClient()
