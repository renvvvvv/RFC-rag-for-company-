import json
import logging
from typing import Any, AsyncIterator, Dict, List

import httpx

from app.config import settings
from app.core.runtime_config import get_model_config

logger = logging.getLogger(__name__)


class LLMClient:
    """minimax-m3 LLM客户端（OpenAI兼容API）"""

    def __init__(self):
        self.timeout = 120.0

    def _config(self):
        cfg = get_model_config()
        base_url = cfg.get("MINIMAX_BASE_URL") or settings.MINIMAX_BASE_URL
        if base_url:
            base_url = base_url.rstrip("/")
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]
        default_url = f"{base_url}/v1/chat/completions"
        # LLM_API_URL is treated as a full endpoint URL and used as-is when set.
        return {
            "api_url": cfg.get("LLM_API_URL") or default_url,
            "model": cfg.get("LLM_MODEL") or settings.LLM_MODEL,
            "api_key": cfg.get("LLM_API_KEY") or cfg.get("MINIMAX_API_KEY") or settings.MINIMAX_API_KEY,
        }

    def _headers(self, api_key: str):
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> Dict[str, Any]:
        cfg = self._config()
        payload = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(cfg["api_url"], json=payload, headers=self._headers(cfg["api_key"]))
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.exception(f"LLM API call failed: {e}")
            raise

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> AsyncIterator[str]:
        cfg = self._config()
        payload = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", cfg["api_url"], json=payload, headers=self._headers(cfg["api_key"])) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except Exception:
                                pass
        except Exception as e:
            logger.exception(f"LLM stream API call failed: {e}")
            yield f"[生成失败: {str(e)}]"


llm_client = LLMClient()
