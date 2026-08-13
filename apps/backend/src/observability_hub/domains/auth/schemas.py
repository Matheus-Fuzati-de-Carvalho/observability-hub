from pydantic import BaseModel


class UserInfo(BaseModel):
    email: str
    name: str
    picture: str | None = None


class TokenResponse(BaseModel):
    """Body de POST /auth/callback — o JWT em si vai só no cookie httpOnly
    (Set-Cookie), nunca no body: o frontend não precisa (nem deve) ler o
    token diretamente."""

    user: UserInfo
