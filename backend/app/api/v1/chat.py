from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.api.v1.auth import get_current_user
from app.schemas.user import UserResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.compression_service import compression_service
from app.services.generation_service import generation_service
from app.services.retrieval_service import retrieval_service
from app.services.security_gateway import security_gateway

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """非流式问答"""
    chunks = await retrieval_service.search(
        db=db,
        user_id=current_user.id,
        query=request.query,
        kb_ids=request.kb_ids,
        modalities=request.modalities,
        top_k=request.top_k or 10,
        rerank_top_k=request.rerank_top_k or 5
    )
    
    strategy = await security_gateway.decide_api_strategy(
        db, current_user.id, chunks, request.query
    )
    
    if strategy["strategy"] == "local_only":
        return ChatResponse(
            answer="当前查询涉及绝密内容，禁止调用外部API生成回答。",
            intercepted=True,
            sources=[],
            strategy=strategy
        )
    
    # 压缩上下文（虽然生成服务也会构建，这里可用于日志/审计）
    compressed_context = compression_service.compress_chunks(
        chunks, max_tokens=request.max_context_tokens or 4000
    )
    
    result = await generation_service.generate_answer(
        db=db,
        query=request.query,
        context_chunks=chunks,
        user_id=current_user.id,
        stream=False
    )
    
    return ChatResponse(
        answer=result["answer"],
        intercepted=result["intercepted"],
        sources=result["sources"],
        strategy=strategy
    )

@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """流式问答"""
    chunks = await retrieval_service.search(
        db=db,
        user_id=current_user.id,
        query=request.query,
        kb_ids=request.kb_ids,
        modalities=request.modalities,
        top_k=request.top_k or 10,
        rerank_top_k=request.rerank_top_k or 5
    )
    
    strategy = await security_gateway.decide_api_strategy(
        db, current_user.id, chunks, request.query
    )
    
    if strategy["strategy"] == "local_only":
        async def local_response():
            yield {"data": "当前查询涉及绝密内容，禁止调用外部API生成回答。"}
        return EventSourceResponse(local_response())
    
    async def event_generator():
        stream_iter = await generation_service.generate_answer(
            db=db,
            query=request.query,
            context_chunks=chunks,
            user_id=current_user.id,
            stream=True
        )
        async for token in stream_iter:
            yield {"data": token}
    
    return EventSourceResponse(event_generator())
