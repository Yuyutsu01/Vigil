"""Evaluation package: corpus loading, classification metrics, and runner."""
from app.evaluation.corpus import CorpusLoader, CorpusTestCase
from app.evaluation.metrics import MetricSummary, compute_metrics
from app.evaluation.runner import EvaluationRunner

__all__ = [
    "CorpusLoader",
    "CorpusTestCase",
    "MetricSummary",
    "compute_metrics",
    "EvaluationRunner",
]
