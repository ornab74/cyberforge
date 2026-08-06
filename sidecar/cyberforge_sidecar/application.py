from __future__ import annotations

from .api import app
from .infrastructure_api import router as infrastructure_router
from .research_api import router as research_router

app.include_router(infrastructure_router)
app.include_router(research_router)

__all__ = ["app"]
