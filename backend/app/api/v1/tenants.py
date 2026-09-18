"""
Tenant operations router (FR-109).
Provides tenant-scoped learning data deletion (GDPR Art. 17 / Right to be Forgotten).
"""
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.redis_client import get_redis
from app.services.learning_service import purge_tenant_learning_data

router = APIRouter(prefix="/v1/tenants", tags=["tenants"])


class PurgeLearningDataResponse(BaseModel):
    status: str
    purged_count: int


@router.delete(
    "/me/learning-data",
    response_model=PurgeLearningDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Purge all governed learning data for this tenant (FR-109)",
)
async def purge_my_learning_data(
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> PurgeLearningDataResponse:
    """
    Purges all indexed precedents from Redis and resets the tenant's learning index.
    Guaranteed completion in under 5 seconds.
    """
    redis = get_redis()
    purged = await purge_tenant_learning_data(db, redis, auth.tenant_id, auth.user_id)
    return PurgeLearningDataResponse(status="purged", purged_count=purged)
