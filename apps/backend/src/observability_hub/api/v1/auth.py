from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import RedirectResponse, Response

from observability_hub.core.auth import get_current_user
from observability_hub.domains.auth import service
from observability_hub.domains.auth.schemas import TokenResponse, UserInfo

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# SameSite=None é obrigatório aqui: frontend e backend são origens
# diferentes (dois serviços Cloud Run distintos) — o cookie precisa
# trafegar em requests cross-site (fetch com credentials:"include").
# SameSite=None exige Secure (só HTTPS, o que o Cloud Run já garante).
_COOKIE_KWARGS = {"httponly": True, "secure": True, "samesite": "none", "path": "/"}


@router.get("/login")
def login() -> RedirectResponse:
    state = service.generate_state()
    response = RedirectResponse(service.build_authorize_url(state))
    response.set_cookie(
        service.STATE_COOKIE_NAME,
        state,
        max_age=service.STATE_COOKIE_MAX_AGE_SECONDS,
        **_COOKIE_KWARGS,
    )
    return response


@router.get("/callback", response_model=TokenResponse)
def callback(
    code: str,
    state: str,
    oauth_state: str | None = Cookie(default=None, alias=service.STATE_COOKIE_NAME),
) -> Response:
    user = service.handle_callback(code, state, oauth_state)
    token = service.issue_session_token(user)

    response = Response(
        content=TokenResponse(user=user).model_dump_json(), media_type="application/json"
    )
    response.delete_cookie(service.STATE_COOKIE_NAME, path="/")
    response.set_cookie(
        service.SESSION_COOKIE_NAME,
        token,
        max_age=service.SESSION_COOKIE_MAX_AGE_SECONDS,
        **_COOKIE_KWARGS,
    )
    return response


@router.get("/me", response_model=UserInfo)
def me(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    return user


@router.post("/logout")
def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(service.SESSION_COOKIE_NAME, path="/")
    return response
