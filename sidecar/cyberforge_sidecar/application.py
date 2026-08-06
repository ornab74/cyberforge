from __future__ import annotations

from .api import app
from .infrastructure_api import router as infrastructure_router

app.include_router(infrastructure_router)

__all__ = ["app"]
