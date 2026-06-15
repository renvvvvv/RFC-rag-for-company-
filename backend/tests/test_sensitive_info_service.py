"""Tests for sensitive information detection service."""
import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.chunk import Chunk
from app.services.sensitive_info_service import (
    PATTERNS,
    SensitiveFinding,
    SensitiveInfoService,
)


class MockKeyword:
    def __init__(
        self,
        keyword,
        level="L2",
        category="custom",
        match_type="exact",
        variants=None,
        action="audit",
    ):
        self.id = uuid.uuid4()
        self.keyword = keyword
        self.level = level
        self.category = category
        self.match_type = match_type
        self.variants = variants or []
        self.action = action


def _service_with_keywords(keywords):
    db = AsyncMock()
    svc = SensitiveInfoService(db)
    svc._keywords = keywords
    return svc


@pytest.mark.asyncio
async def test_scan_pii_id_card():
    svc = _service_with_keywords([])
    text = "身份证号 110101199001011234 需要保密"
    findings = await svc.scan_text(text)
    id_cards = [f for f in findings if f["label"] == "id_card"]
    assert len(id_cards) == 1
    assert id_cards[0]["matched_text"] == "110101199001011234"
    assert id_cards[0]["severity"] == "L3"


@pytest.mark.asyncio
async def test_scan_pii_phone_and_email():
    svc = _service_with_keywords([])
    text = "联系：13800138000 或 admin@example.com"
    findings = await svc.scan_text(text)
    labels = {f["label"] for f in findings}
    assert "phone" in labels
    assert "email" in labels


@pytest.mark.asyncio
async def test_scan_keywords_exact_and_variant():
    svc = _service_with_keywords(
        [
            MockKeyword("机密", level="L3", category="confidential"),
            MockKeyword("薪酬", level="L2", variants=["工资", "月收入"]),
        ]
    )
    text = "工资和月收入属于薪酬信息，是机密的"
    findings = await svc.scan_text(text)
    keywords = [f for f in findings if f["type"] == "keyword"]
    assert len(keywords) >= 3
    assert any(f["matched_text"] == "机密" for f in keywords)


@pytest.mark.asyncio
async def test_scan_keywords_regex():
    svc = _service_with_keywords(
        [
            MockKeyword(
                keyword=r"\bproj-\d{4}\b",
                level="L2",
                category="project",
                match_type="regex",
            )
        ]
    )
    text = "项目编号 proj-2024 已立项"
    findings = await svc.scan_text(text)
    regex_findings = [f for f in findings if f.get("metadata", {}).get("keyword") == r"\bproj-\d{4}\b"]
    assert len(regex_findings) == 1
    assert regex_findings[0]["matched_text"] == "proj-2024"


@pytest.mark.asyncio
async def test_mask_text():
    svc = _service_with_keywords([])
    text = "联系我 13800138000"
    findings = await svc.scan_text(text)
    masked = svc.mask_text(text, findings)
    assert "13800138000" not in masked
    assert "[PHONE]" in masked


@pytest.mark.asyncio
async def test_mask_text_no_findings():
    svc = _service_with_keywords([])
    text = "普通文本"
    assert svc.mask_text(text, []) == text


@pytest.mark.asyncio
async def test_scan_document_content():
    svc = _service_with_keywords([])
    doc_id = uuid.uuid4()
    chunks = ["我的手机 13800138000", "普通内容"]
    findings = await svc.scan_document_content(doc_id, chunks)
    assert len(findings) == 1
    assert findings[0]["doc_id"] == str(doc_id)
    assert findings[0]["chunk_index"] == 0


@pytest.mark.asyncio
async def test_scan_chunks_attaches_metadata():
    svc = _service_with_keywords(
        [MockKeyword("机密", level="L3", category="confidential")]
    )
    chunks = [
        Chunk(content="这是机密文件", metadata_={}),
        Chunk(content="普通文件", metadata_={}),
    ]
    all_findings = await svc.scan_chunks(chunks)
    assert len(all_findings) == 1
    assert chunks[0].metadata_["has_sensitive_findings"] is True
    assert chunks[0].metadata_["max_builtin_severity"] == "L3"
    assert chunks[1].metadata_.get("has_sensitive_findings") is None


def test_pattern_bank_card():
    text = "卡号 6222021234567890123 已过期"
    matches = list(PATTERNS["bank_card"].finditer(text))
    assert len(matches) >= 1


def test_deduplicate_findings_helper():
    from app.services.sensitive_info_service import _deduplicate_findings

    findings = [
        {"start": 0, "end": 5, "label": "a"},
        {"start": 1, "end": 4, "label": "b"},
        {"start": 10, "end": 15, "label": "c"},
    ]
    cleaned = _deduplicate_findings(findings)
    assert len(cleaned) == 2
    labels = {f["label"] for f in cleaned}
    assert "a" in labels
    assert "c" in labels


def test_sensitive_finding_to_dict():
    finding = SensitiveFinding(
        type="pii",
        label="phone",
        matched_text="13800138000",
        start=0,
        end=11,
        severity="L2",
    )
    data = finding.to_dict()
    assert data["type"] == "pii"
    assert data["matched_text"] == "13800138000"
