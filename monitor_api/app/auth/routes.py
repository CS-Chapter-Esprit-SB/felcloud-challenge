from auth0_fastapi.errors import register_exception_handlers  # pyright: ignore[reportMissingTypeStubs]
from auth0_fastapi.server.routes import (
    register_auth_routes,
    router as auth_router,
)  # pyright: ignore[reportMissingTypeStubs]

from monitor_api.app.auth.client import auth0_config


register_auth_routes(auth_router, auth0_config)  # pyright: ignore[reportArgumentType]


__all__ = [
    "auth_router",
    "register_exception_handlers",
]