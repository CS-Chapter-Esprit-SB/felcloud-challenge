from typing import Any

from fastapi import APIRouter, Depends

from monitor_api.app.auth.dependencies import require_authenticated_user

router = APIRouter(tags=["Users"])


@router.get("/me")
async def get_current_user(
    user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    return {
        "authenticated": True,
        "user": user,
    }