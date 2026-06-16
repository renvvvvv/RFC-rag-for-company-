"""Mock LLM service for local integration testing.

Implements a minimal OpenAI-compatible chat completions endpoint.
"""
import json
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Mock LLM Service")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "mock-llm"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.3
    max_tokens: Optional[int] = 2000
    stream: Optional[bool] = False


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest) -> Dict[str, Any]:
    query = ""
    for m in reversed(req.messages):
        if m.role == "user":
            query = m.content
            break

    if req.stream:
        return StreamingResponse(
            _stream_answer(query),
            media_type="text/event-stream",
        )

    return {
        "id": "mock-chatcmpl",
        "object": "chat.completion",
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": _build_answer(query),
                },
                "finish_reason": "stop",
            }
        ],
    }


async def _stream_answer(query: str) -> AsyncIterator[str]:
    answer = _build_answer(query)
    for word in answer:
        chunk = {
            "id": "mock-chatcmpl",
            "object": "chat.completion.chunk",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": word},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def _build_answer(query: str) -> str:
    return (
        "这是一个由本地 Mock LLM 生成的测试回答。"
        "基于你提供的问题，我给出了一段固定回复用于验证 RAG 流程。"
    )
