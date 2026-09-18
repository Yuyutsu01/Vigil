"""API v1 router aggregator."""
from fastapi import APIRouter

from app.api.v1 import auth, consent, reviews, uploads

v1_router = APIRouter()
v1_router.include_router(auth.router)
v1_router.include_router(consent.router)
v1_router.include_router(reviews.router)
v1_router.include_router(uploads.router)

__all__ = ["v1_router"]
