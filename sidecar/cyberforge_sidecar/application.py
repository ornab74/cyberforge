from __future__ import annotations

from .api import app
from .infrastructure_api import router as infrastructure_router
from .memory_governance_api import router as memory_governance_router
from .phishing_federation_api import router as phishing_federation_router
from .phishing_rod_api import router as phishing_rod_router
from .research_api import router as research_router
from .storage_api import router as storage_router

app.include_router(infrastructure_router)
app.include_router(research_router)
app.include_router(storage_router)
app.include_router(memory_governance_router)
app.include_router(phishing_rod_router)
app.include_router(phishing_federation_router)

__all__ = ["app"]
