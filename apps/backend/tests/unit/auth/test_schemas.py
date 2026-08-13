from observability_hub.domains.auth.schemas import TokenResponse, UserInfo


def test_user_info_picture_defaults_to_none():
    user = UserInfo(email="a@dp6.com.br", name="A")
    assert user.picture is None


def test_token_response_wraps_user():
    user = UserInfo(email="a@dp6.com.br", name="A", picture="https://example.com/p.png")
    response = TokenResponse(user=user)
    assert response.user.email == "a@dp6.com.br"
