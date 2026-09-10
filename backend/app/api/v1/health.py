from fastapi import APIRouter, status
from backend.app.core.config import settings
from backend.app.models.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Returns the operational status, semantic version, and runtime environment of the API.",
)
async def health_check() -> HealthResponse:
    """Check API health and runtime readiness."""
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )
