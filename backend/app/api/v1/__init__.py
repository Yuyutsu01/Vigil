"""API v1 router aggregator."""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    consent,
    evaluation,
    findings,
    patches,
    pr_reviews,
    repositories,
    reviews,
    stats,
    tenants,
    uploads,
    webhooks,
)

v1_router = APIRouter()
v1_router.include_router(auth.router)
v1_router.include_router(consent.router)
v1_router.include_router(tenants.router)
v1_router.include_router(stats.router)
v1_router.include_router(reviews.router)
v1_router.include_router(findings.router)
v1_router.include_router(uploads.router)
v1_router.include_router(evaluation.router)
v1_router.include_router(repositories.router)
v1_router.include_router(webhooks.router)
v1_router.include_router(patches.router)
v1_router.include_router(pr_reviews.router)

__all__ = ["v1_router"]
