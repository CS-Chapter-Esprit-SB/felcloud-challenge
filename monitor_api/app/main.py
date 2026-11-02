from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from monitor_api.app.api.routes import health, monitoring, users
from monitor_api.app.auth.client import auth0_client, auth0_config
from monitor_api.app.auth.routes import auth_router, register_exception_handlers
from monitor_api.app.config import settings
from monitor_api.shared.database import Base, engine
from monitor_api.shared.models import Instance,ConsumerState,ActivityEvent,Index  # Ensure models are registered with SQLAlchemy


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.AUTH0_SECRET,
    same_site="lax",
    https_only=str(settings.APP_BASE_URL).startswith("https://"),
)

app.state.config = auth0_config
app.state.auth_client = auth0_client

# Authentication routes
app.include_router(auth_router)

# Application routes
app.include_router(health.router)
app.include_router(users.router)
app.include_router(monitoring.router)

register_exception_handlers(app)