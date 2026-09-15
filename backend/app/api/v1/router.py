from fastapi import APIRouter
from backend.app.api.v1 import agent, auth, health

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(agent.router, tags=["Agent"])
