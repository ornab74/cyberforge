from __future__ import annotations

import uvicorn

from .config import SETTINGS


def main() -> None:
    uvicorn.run(
        "cyberforge_sidecar.application:app",
        host=SETTINGS.bind_host,
        port=SETTINGS.port,
        reload=False,
        access_log=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
