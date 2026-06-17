import asyncio
import logging
from typing import Any, Dict, List

import httpx

from app.config import settings
from app.core.runtime_config import get_model_config

logger = logging.getLogger(__name__)


class RerankClient:
    """用户提供的Re-rank模型HTTP客户端"""

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
            "api_url": cfg.get("RERANK_API_URL") or settings.RERANK_SERVICE_URL,
            "model": cfg.get("RERANK_MODEL") or settings.RERANK_MODEL,
            "api_key": cfg.get("RERANK_API_KEY") or settings.RERANK_API_KEY,
        }

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        if not documents:
            return []

        cfg = self._config()
        headers = {"Content-Type": "application/json"}
        if cfg["api_key"]:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"

        payload = {
            "model": cfg["model"],
            "query": query,
            "documents": [d.get("content", "") for d in documents],
            "top_n": top_k,
        }

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        cfg["api_url"], json=payload, headers=headers
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    if "results" in data:
                        results = []
                        for r in data["results"]:
                            idx = r.get("index", 0)
                            if 0 <= idx < len(documents):
                                item = documents[idx].copy()
                                item["rerank_score"] = r.get("relevance_score", 0.0)
                                results.append(item)
                        return results
                    elif isinstance(data, list):
                        results = []
                        for i, score in enumerate(data):
                            if i < len(documents):
                                item = documents[i].copy()
                                item["rerank_score"] = score
                                results.append(item)
                        return sorted(results, key=lambda x: x["rerank_score"], reverse=True)[:top_k]
                    else:
                        logger.warning("Unknown rerank response format")
                        return documents[:top_k]
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries and self._should_retry(e):
                    delay = self.base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Rerank API attempt %s/%s failed (%s); retrying in %.1fs",
                        attempt,
                        self.max_retries,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                break

        logger.exception("Rerank API call failed after %s attempts: %s", self.max_retries, last_exc)
        return sorted(documents, key=lambda x: x.get("score", 0), reverse=True)[:top_k]


rerank_client = RerankClient()
