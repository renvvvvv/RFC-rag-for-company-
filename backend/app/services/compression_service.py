from typing import List, Dict, Any

class CompressionService:
    """上下文压缩服务：权限标记内联、按级别分组压缩"""
    
    def compress_chunks(
        self,
        chunks: List[Dict[str, Any]],
        max_tokens: int = 4000,
        strategy: str = "permission_aware"
    ) -> str:
        if strategy == "permission_aware":
            return self._permission_aware_compress(chunks, max_tokens)
        else:
            return self._simple_truncate(chunks, max_tokens)
    
    def _permission_aware_compress(
        self,
        chunks: List[Dict[str, Any]],
        max_tokens: int
    ) -> str:
        # 按敏感级别降序，同级别按分数降序
        sorted_chunks = sorted(
            chunks,
            key=lambda x: (
                -(x.get("max_keyword_level_value") or 0),
                -(x.get("rerank_score") or x.get("score", 0))
            )
        )
        
        def estimate_tokens(text: str) -> int:
            return int(len(text) * 1.5)
        
        parts = []
        current_tokens = 0
        
        for chunk in sorted_chunks:
            level = chunk.get("max_keyword_level", "L0")
            content = chunk.get("content", "").strip()
            if not content:
                continue
            
            compressed = self._compress_single(content, max_len=300)
            wrapped = f'<chunk level="{level}">\n<perm level="{level}"/>\n{compressed}\n</chunk>'
            token_count = estimate_tokens(wrapped)
            
            if current_tokens + token_count > max_tokens:
                break
            
            parts.append(wrapped)
            current_tokens += token_count
        
        return "\n\n".join(parts)
    
    def _compress_single(self, text: str, max_len: int = 300) -> str:
        if len(text) <= max_len:
            return text
        head = text[:max_len // 2]
        tail = text[-max_len // 2:]
        return f"{head}\n...[省略]...\n{tail}"
    
    def _simple_truncate(self, chunks: List[Dict[str, Any]], max_tokens: int) -> str:
        parts = []
        current_len = 0
        for chunk in chunks:
            text = chunk.get("content", "")
            if current_len + len(text) > max_tokens * 0.7:
                break
            parts.append(text)
            current_len += len(text)
        return "\n\n".join(parts)

compression_service = CompressionService()
