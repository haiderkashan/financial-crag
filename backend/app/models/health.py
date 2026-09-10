from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check payload response model."""

    status: str = Field(..., description="Service status indicator")
    version: str = Field(..., description="API semantic version")
    environment: str = Field(..., description="Current runtime environment")
