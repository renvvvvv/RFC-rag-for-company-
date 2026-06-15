"""Sensitive information detection service.

Detects PII (ID card, phone, email, bank card), custom sensitive keywords,
and optional named entities via spaCy.  When spaCy is unavailable or the
requested model is not installed, the service falls back to regex-based
patterns.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword import SensitiveKeyword

if TYPE_CHECKING:
    from app.models.chunk import Chunk

logger = logging.getLogger(__name__)


# Regex patterns for common PII / finance / medical indicators.
# These are intentionally conservative to reduce false positives.
PATTERNS = {
    "id_card": re.compile(
        r"\b[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"
    ),
    "phone": re.compile(r"\b1[3-9]\d{9}\b"),
    "email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    ),
    "bank_card": re.compile(
        r"\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|6(?:011|5\d{2}|2\d{1})\d{13,16}|3[47]\d{13}|3(?:0[0-5]|[68]\d)\d{11}|(?:2131|1800|35\d{3})\d{11})\b"
    ),
}

# Optional spaCy model.  Loaded lazily and never required.
_SPACY_MODEL = None
_SPACY_AVAILABLE: Optional[bool] = None


def _load_spacy_model(model_name: str = "zh_core_web_sm"):
    """Load a spaCy NER model, returning None if it cannot be used."""
    global _SPACY_MODEL, _SPACY_AVAILABLE
    if _SPACY_AVAILABLE is not None:
        return _SPACY_MODEL

    try:
        import spacy

        _SPACY_MODEL = spacy.load(model_name)
        _SPACY_AVAILABLE = True
    except Exception as exc:  # noqa: BLE001
        logger.debug("spaCy NER unavailable: %s", exc)
        _SPACY_AVAILABLE = False
        _SPACY_MODEL = None
    return _SPACY_MODEL


@dataclass
class SensitiveFinding:
    """A single sensitive information finding."""

    type: str
    label: str
    matched_text: str
    start: int
    end: int
    severity: str = "L1"
    confidence: float = 1.0
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "label": self.label,
            "matched_text": self.matched_text,
            "start": self.start,
            "end": self.end,
            "severity": self.severity,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class SensitiveInfoService:
    """Scan text, documents, and chunks for sensitive information.

    The service combines:
    1. Rule-based PII detection (regex).
    2. Custom keyword matching from the ``SensitiveKeyword`` table.
    3. Optional NER detection through spaCy (falls back to no entities).
    """

    # Severity mapping for built-in PII types.
    SEVERITY_MAP = {
        "id_card": "L3",
        "phone": "L2",
        "email": "L2",
        "bank_card": "L3",
    }

    def __init__(
        self,
        db: AsyncSession,
        spacy_model_name: Optional[str] = "zh_core_web_sm",
    ) -> None:
        self.db = db
        self.spacy_model_name = spacy_model_name
        self._keywords: Optional[List[SensitiveKeyword]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def scan_text(self, text: str) -> List[Dict]:
        """Scan free text and return a list of finding dictionaries."""
        if not text or not text.strip():
            return []

        findings: List[SensitiveFinding] = []
        findings.extend(self._scan_pii(text))
        findings.extend(await self._scan_keywords(text))
        findings.extend(self._scan_ner(text))
        findings.sort(key=lambda f: f.start)
        return [f.to_dict() for f in findings]

    async def scan_document_content(
        self,
        doc_id: UUID,
        chunks: List[str],
    ) -> List[Dict]:
        """Scan a list of chunk strings for a document.

        Returns findings enriched with ``doc_id`` and ``chunk_index``.
        """
        results: List[Dict] = []
        for idx, content in enumerate(chunks):
            chunk_findings = await self.scan_text(content)
            for finding in chunk_findings:
                finding["doc_id"] = str(doc_id)
                finding["chunk_index"] = idx
                results.append(finding)
        return results

    async def scan_chunks(self, chunks: List["Chunk"]) -> List[Dict]:
        """Scan a list of ``Chunk`` records and attach findings to metadata."""
        all_findings: List[Dict] = []
        for chunk in chunks:
            findings = await self.scan_text(chunk.content or "")
            if findings:
                meta = chunk.metadata_ or {}
                existing = meta.get("sensitive_findings", [])
                existing.extend(findings)
                meta["sensitive_findings"] = existing
                meta["has_sensitive_findings"] = True
                meta["max_builtin_severity"] = self._max_severity(existing)
                chunk.metadata_ = meta
                for finding in findings:
                    finding["chunk_id"] = str(chunk.id)
                all_findings.extend(findings)
        return all_findings

    def mask_text(self, text: str, findings: List[Dict]) -> str:
        """Mask sensitive findings in ``text`` with a generic token.

        Findings must contain ``start`` and ``end`` positions.  They are
        applied in reverse order so earlier masks do not shift later spans.
        """
        if not findings:
            return text

        masked = text
        for finding in sorted(findings, key=lambda f: f.get("start", 0), reverse=True):
            start = finding.get("start")
            end = finding.get("end")
            label = finding.get("label", finding.get("type", "SENSITIVE"))
            if start is None or end is None:
                continue
            masked = masked[:start] + f"[{label.upper()}]" + masked[end:]
        return masked

    # ------------------------------------------------------------------
    # Built-in detectors
    # ------------------------------------------------------------------
    def _scan_pii(self, text: str) -> List[SensitiveFinding]:
        findings: List[SensitiveFinding] = []
        for pii_type, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append(
                    SensitiveFinding(
                        type="pii",
                        label=pii_type,
                        matched_text=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        severity=self.SEVERITY_MAP.get(pii_type, "L1"),
                        confidence=1.0,
                    )
                )
        return findings

    async def _scan_keywords(self, text: str) -> List[SensitiveFinding]:
        """Scan text against keywords stored in the database."""
        keywords = await self._load_keywords()
        findings: List[SensitiveFinding] = []
        lower_text = text.lower()

        for kw in keywords:
            patterns = {kw.keyword.lower()}
            patterns.update((v or "").lower() for v in (kw.variants or []))
            patterns.discard("")

            for pattern in patterns:
                if kw.match_type == "regex":
                    try:
                        compiled = re.compile(pattern, re.IGNORECASE)
                    except re.error:
                        continue
                    for match in compiled.finditer(text):
                        findings.append(
                            SensitiveFinding(
                                type="keyword",
                                label=kw.category or "custom",
                                matched_text=match.group(0),
                                start=match.start(),
                                end=match.end(),
                                severity=kw.level,
                                confidence=1.0,
                                metadata={
                                    "keyword_id": str(kw.id),
                                    "keyword": kw.keyword,
                                    "action": kw.action,
                                },
                            )
                        )
                else:
                    start = 0
                    while True:
                        idx = lower_text.find(pattern, start)
                        if idx == -1:
                            break
                        end = idx + len(pattern)
                        findings.append(
                            SensitiveFinding(
                                type="keyword",
                                label=kw.category or "custom",
                                matched_text=text[idx:end],
                                start=idx,
                                end=end,
                                severity=kw.level,
                                confidence=1.0,
                                metadata={
                                    "keyword_id": str(kw.id),
                                    "keyword": kw.keyword,
                                    "action": kw.action,
                                },
                            )
                        )
                        start = end
        return findings

    def _scan_ner(self, text: str) -> List[SensitiveFinding]:
        """Scan text using spaCy NER.  Falls back to empty list on failure."""
        model = _load_spacy_model(self.spacy_model_name or "zh_core_web_sm")
        if model is None:
            return []

        findings: List[SensitiveFinding] = []
        doc = model(text)
        sensitive_labels = {"PERSON", "ORG", "GPE", "LOC", "PHONE", "EMAIL", "ID"}
        for ent in doc.ents:
            if ent.label_ in sensitive_labels:
                findings.append(
                    SensitiveFinding(
                        type="ner",
                        label=ent.label_.lower(),
                        matched_text=ent.text,
                        start=ent.start_char,
                        end=ent.end_char,
                        severity="L1",
                        confidence=0.85,
                    )
                )
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _load_keywords(self) -> List[SensitiveKeyword]:
        if self._keywords is None:
            result = await self.db.execute(select(SensitiveKeyword))
            self._keywords = list(result.scalars().all())
        return self._keywords

    @staticmethod
    def _max_severity(findings: List[Dict]) -> str:
        order = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}
        if not findings:
            return "L0"
        return max(
            findings,
            key=lambda f: order.get(f.get("severity", "L0"), -1),
        ).get("severity", "L0")


def _deduplicate_findings(findings: List[Dict]) -> List[Dict]:
    """Remove overlapping findings, keeping the longer match."""
    if not findings:
        return findings

    sorted_findings = sorted(findings, key=lambda f: (f.get("start", 0), -(f.get("end", 0) - f.get("start", 0))))
    cleaned: List[Dict] = []
    for f in sorted_findings:
        start, end = f.get("start", 0), f.get("end", 0)
        if any(
            existing.get("start", 0) <= start < existing.get("end", 0)
            or existing.get("start", 0) < end <= existing.get("end", 0)
            for existing in cleaned
        ):
            continue
        cleaned.append(f)
    return cleaned
