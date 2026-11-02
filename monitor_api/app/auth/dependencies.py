from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, Response

from monitor_api.app.auth.client import auth0_client


async def require_authenticated_user(
    request: Request,
    response: Response,
    _session: dict = Depends(auth0_client.require_session),  # pyright: ignore[reportMissingTypeArgument]
) -> dict[str, Any]:
    """Require a valid Auth0 session."""

    user = await auth0_client.client.get_user(
        store_options={
            "request": request,
            "response": response,
        },
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    return user