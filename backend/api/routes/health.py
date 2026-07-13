"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.dependencies import check_health_components

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    """Return component health checks."""

    components = check_health_components()
    critical = [components["application"], components["sqlite"], components["chromadb"]]
    if any(status == "unhealthy" for status in critical):
        status = "unhealthy"
    elif components["openai_configuration"] != "available":
        status = "degraded"
    else:
        status = "healthy"
    return {
        "status": status,
        "components": components,
    }
