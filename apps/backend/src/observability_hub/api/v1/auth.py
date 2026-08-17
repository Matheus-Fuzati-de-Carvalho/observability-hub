from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import RedirectResponse, Response
from google.cloud import firestore

from observability_hub.core.auth import get_current_user
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.admin import analytics_service
from observability_hub.domains.admin import service as admin_service
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
    client: firestore.Client = Depends(get_firestore_client),
) -> Response:
    user = service.handle_callback(code, state, oauth_state)
    token = service.issue_session_token(user)
    analytics_service.record_login(client, user.email)

    response = Response(
        content=TokenResponse(user=user).model_dump_json(), media_type="application/json"
    )
    response.delete_cookie(service.STATE_COOKIE_NAME, **_COOKIE_KWARGS)
    response.set_cookie(
        service.SESSION_COOKIE_NAME,
        token,
        max_age=service.SESSION_COOKIE_MAX_AGE_SECONDS,
        **_COOKIE_KWARGS,
    )
    return response


@router.get("/me", response_model=UserInfo)
def me(
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> UserInfo:
    return user.model_copy(update={"is_admin": admin_service.is_admin(client, user.email)})


@router.post("/logout")
def logout() -> Response:
    response = Response(status_code=204)
    # delete_cookie precisa dos MESMOS atributos secure/httponly/samesite do
    # cookie original (Starlette default é secure=False/httponly=False/
    # samesite="lax") — sem isso o browser não reconhece como o mesmo
    # cookie e o Set-Cookie de deleção é ignorado, deixando a sessão viva.
    response.delete_cookie(service.SESSION_COOKIE_NAME, **_COOKIE_KWARGS)
    return response
