from auth0_fastapi.auth.auth_client import AuthClient  # pyright: ignore[reportMissingTypeStubs]
from auth0_fastapi.config import Auth0Config

from monitor_api.app.config import settings


auth0_config = Auth0Config(
    domain=settings.AUTH0_DOMAIN,
    client_id=settings.AUTH0_CLIENT_ID,
    client_secret=settings.AUTH0_CLIENT_SECRET,
    secret=settings.AUTH0_SECRET,
    app_base_url=settings.APP_BASE_URL,  # pyright: ignore[reportArgumentType]
    audience=None,
    authorization_params={
        "scope": "openid profile email",
    },
)

auth0_client = AuthClient(auth0_config)