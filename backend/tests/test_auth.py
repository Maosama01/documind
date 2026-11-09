import pytest

EMAIL = "ada@example.com"
PASSWORD = "correct horse battery staple"


def signup(client):
    return client.post(
        "/auth/signup",
        json={"email": EMAIL, "full_name": "Ada Lovelace", "password": PASSWORD},
    )


def test_login_schema_asks_only_for_email_and_password():
    from app.main import app

    schema = app.openapi()
    body = schema["paths"]["/auth/login"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert body["$ref"].endswith("/UserLogin")
    assert set(schema["components"]["schemas"]["UserLogin"]["required"]) == {"email", "password"}


@pytest.mark.db
def test_login_with_email_and_password_returns_a_working_token(client):
    assert signup(client).status_code == 201

    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 200
    token = response.json()
    assert token["token_type"] == "bearer"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


def test_creating_a_token_raises_no_deprecation_warning():
    """datetime.utcnow() is deprecated; the expiry now uses a timezone-aware time."""
    import warnings
    from datetime import timedelta

    from jose import jwt

    from app.config import settings
    from app.services.auth_service import create_access_token

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        token = create_access_token({"sub": EMAIL}, expires_delta=timedelta(minutes=5))

    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims["sub"] == EMAIL


def test_swagger_logs_in_through_the_form_endpoint():
    """Swagger's Authorize button posts the OAuth2 form to the scheme's tokenUrl."""
    from app.main import app

    schemes = app.openapi()["components"]["securitySchemes"]
    assert len(schemes) == 1  # one login for every protected route, /auth/me included
    (scheme,) = schemes.values()
    assert scheme["flows"]["password"]["tokenUrl"] == "/auth/token"


@pytest.mark.db
def test_form_login_like_swaggers_authorize_button(client):
    assert signup(client).status_code == 201

    # The same fields Swagger UI sends for the OAuth2 password flow
    response = client.post(
        "/auth/token",
        data={"grant_type": "password", "username": EMAIL, "password": PASSWORD, "scope": ""},
    )

    assert response.status_code == 200
    token = response.json()
    assert token["token_type"] == "bearer"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


@pytest.mark.db
def test_form_login_with_wrong_password_is_rejected(client):
    assert signup(client).status_code == 201

    response = client.post("/auth/token", data={"username": EMAIL, "password": "wrong password"})

    assert response.status_code == 401


@pytest.mark.db
def test_me_rejects_an_invalid_token(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


@pytest.mark.db
def test_login_with_wrong_password_is_rejected(client):
    assert signup(client).status_code == 201

    response = client.post("/auth/login", json={"email": EMAIL, "password": "wrong password"})

    assert response.status_code == 401
