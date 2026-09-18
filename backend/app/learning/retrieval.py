"""
Tenant-isolated Precedent Retrieval (FR-109).
Retrieves sanitized historical precedents using rule and AST similarity matching.
Strictly isolated per tenant: Tenant A cannot retrieve Tenant B's precedents.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
import uuid

import redis.asyncio as aioredis

from app.agents.risk_scoring_agent import SanitizedPrecedent
from app.config import Settings, get_settings
from app.redis_client import get_redis

logger = logging.getLogger(__name__)


def compute_precedent_similarity(
    query_rule_id: str,
    query_category: str,
    query_language: str,
    query_ast_path: Optional[str],
    candidate: Dict[str, Any],
) -> float:
    """
    Computes a deterministic similarity score between a target finding and an indexed precedent.
    Weights:
      - rule_id match: 0.50
      - category match: 0.20
      - language match: 0.15
      - ast_path match: 0.15
    """
    score = 0.0

    cand_rule = candidate.get("rule_id", "")
    if query_rule_id and cand_rule and query_rule_id.lower() == cand_rule.lower():
        score += 0.50

    cand_cat = candidate.get("category", "")
    if query_category and cand_cat and query_category.lower() == cand_cat.lower():
        score += 0.20

    cand_lang = candidate.get("language", "")
    if query_language and cand_lang and query_language.lower() == cand_lang.lower():
        score += 0.15

    cand_ast = candidate.get("ast_path")
    if query_ast_path and cand_ast and query_ast_path == cand_ast:
        score += 0.15
    elif not query_ast_path and not cand_ast:
        score += 0.15  # both lack AST paths

    return round(score, 4)


class PrecedentRetriever:
    """
    Retrieves tenant-isolated precedents from Redis vector/hash store.
    """

    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.redis = redis_client or get_redis()
        self.settings = settings or get_settings()
        self.threshold = getattr(self.settings, "rag_match_threshold", 0.82)

    async def retrieve_precedents(
        self,
        tenant_id: uuid.UUID,
        rule_id: str,
        category: str,
        language: str,
        ast_path: Optional[str] = None,
        limit: int = 5,
    ) -> List[SanitizedPrecedent]:
        """
        Queries precedents for a single tenant, matching against finding properties.
        Strictly isolated by tenant_id key space.
        """
        set_key = f"vigil:learning_keys:{tenant_id}"
        keys = await self.redis.smembers(set_key)
        if not keys:
            return []

        scored_precedents: List[SanitizedPrecedent] = []

        for key in keys:
            data_raw = await self.redis.get(key)
            if not data_raw:
                continue
            try:
                data = json.loads(data_raw)
            except Exception:
                continue

            sim = compute_precedent_similarity(
                query_rule_id=rule_id,
                query_category=category,
                query_language=language,
                query_ast_path=ast_path,
                candidate=data,
            )

            # Match threshold check (M1: configurable threshold, default 0.82)
            if sim >= self.threshold:
                try:
                    idx_id = uuid.UUID(data.get("index_id", str(uuid.uuid4())))
                except ValueError:
                    idx_id = uuid.uuid4()

                prec = SanitizedPrecedent(
                    index_id=idx_id,
                    rule_id=data.get("rule_id", rule_id),
                    category=data.get("category", category),
                    language=data.get("language", language),
                    disposition=data.get("disposition", "accepted"),
                    reason_category=data.get("reason_category"),
                    user_comment_sanitized=data.get("user_comment_sanitized"),
                    similarity_score=sim,
                )
                scored_precedents.append(prec)

        # Sort descending by similarity score
        scored_precedents.sort(key=lambda p: p.similarity_score, reverse=True)
        return scored_precedents[:limit]
