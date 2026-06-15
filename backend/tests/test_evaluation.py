"""Tests for evaluation metrics."""
import pytest

from app.services.evaluation_service import EvaluationService


@pytest.fixture
def service():
    return EvaluationService()


def test_recall_at_k(service):
    retrieved = ["c1", "c2", "c3", "c4"]
    gt = ["c2", "c4"]
    assert service.recall_at_k(retrieved, gt, 3) == 0.5
    assert service.recall_at_k(retrieved, gt, 4) == 1.0
    assert service.recall_at_k(retrieved, [], 3) == 0.0


def test_mrr(service):
    assert service.mrr(["c1", "c2", "c3"], ["c2"]) == 0.5
    assert service.mrr(["c1", "c2", "c3"], ["c3"]) == pytest.approx(1 / 3)
    assert service.mrr(["c1", "c2"], ["c3"]) == 0.0


def test_ndcg_at_k(service):
    retrieved = ["c1", "c2", "c3"]
    gt = ["c3", "c1"]
    score = service.ndcg_at_k(retrieved, gt, 3)
    # DCG: c1 at rank 1 -> 1 / log2(2) = 1, c3 at rank 3 -> 1 / log2(4) = 0.5
    # IDCG: c3 at 1 -> 1, c1 at 2 -> 1 / log2(3) ≈ 0.6309
    expected = (1 + 0.5) / (1 + 1 / 1.585)
    assert score == pytest.approx(expected, abs=0.01)


def test_ndcg_at_k_no_relevant(service):
    assert service.ndcg_at_k(["c1", "c2"], ["c3"], 2) == 0.0


@pytest.mark.asyncio
async def test_faithfulness_score_fallback(service):
    # No LLM available in unit test; heuristic fallback should work.
    score = await service.faithfulness_score(
        "The quick brown fox.",
        "The quick brown fox jumps over the lazy dog.",
    )
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_relevance_score_fallback(service):
    score = await service.relevance_score(
        "What color is the fox?",
        "The fox is brown.",
    )
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_coherence_score_fallback(service):
    score = await service.coherence_score("This is a coherent answer. It has two sentences.")
    assert 0.0 <= score <= 1.0
