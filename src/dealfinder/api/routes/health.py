"""Health check endpoint for the Deal Finder API."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Health check")
async def health() -> dict:
    """Return API health status.

    Returns:
        JSON object with ``status`` field set to ``"ok"``.
    """
    return {"status": "ok", "service": "dealfinder-api"}
