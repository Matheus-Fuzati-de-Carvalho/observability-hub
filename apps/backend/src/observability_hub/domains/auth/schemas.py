from pydantic import BaseModel


class UserInfo(BaseModel):
    email: str
    name: str
    picture: str | None = None
    # Default False sempre que UserInfo é construído a partir do JWT de
    # sessão (get_current_user) — só confiável quando devolvido por
    # GET /auth/me, que popula com uma leitura fresca de hub_users
    # (domains/admin). Qualquer checagem de admin de verdade usa
    # core/auth.py::require_admin, nunca este campo.
    is_admin: bool = False


class TokenResponse(BaseModel):
    """Body de POST /auth/callback — o JWT em si vai só no cookie httpOnly
    (Set-Cookie), nunca no body: o frontend não precisa (nem deve) ler o
    token diretamente."""

    user: UserInfo
