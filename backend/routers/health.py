"""Health check router"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
      return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "AI GTM Engineer API",
                "version": "1.0.0"
            }
