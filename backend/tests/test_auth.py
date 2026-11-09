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


@pytest.mark.db
def test_login_with_wrong_password_is_rejected(client):
    assert signup(client).status_code == 201

    response = client.post("/auth/login", json={"email": EMAIL, "password": "wrong password"})

    assert response.status_code == 401
