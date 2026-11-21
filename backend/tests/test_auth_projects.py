import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_register_login_and_me(client: AsyncClient) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "analyst@example.com",
            "password": "StrongPassword123!",
            "full_name": "Ada Analyst",
        },
    )
    assert reg.status_code == 201, reg.text
    reg_data = reg.json()
    assert reg_data["access_token"]
    assert reg_data["user"]["email"] == "analyst@example.com"
    assert "password_hash" not in reg_data["user"]

    # Duplicate email rejected
    dup = await client.post(
        "/api/v1/auth/register",
        json={"email": "analyst@example.com", "password": "StrongPassword123!"},
    )
    assert dup.status_code == 409

    # Login succeeds
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@example.com", "password": "StrongPassword123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    # Wrong password rejected
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["full_name"] == "Ada Analyst"


@pytest.mark.asyncio
async def test_project_crud_and_ownership_isolation(client: AsyncClient) -> None:
    u1 = await client.post(
        "/api/v1/auth/register",
        json={"email": "user1@example.com", "password": "StrongPassword123!"},
    )
    u2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "user2@example.com", "password": "StrongPassword123!"},
    )
    t1 = u1.json()["access_token"]
    t2 = u2.json()["access_token"]

    create_res = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {t1}"},
        json={"title": "AI Automation Study", "description": "Market analysis"},
    )
    assert create_res.status_code == 201
    project_id = create_res.json()["id"]

    # User 1 sees project
    list1 = await client.get("/api/v1/projects", headers={"Authorization": f"Bearer {t1}"})
    assert len(list1.json()) == 1

    # User 2 cannot access, update, or delete User 1's project
    assert (
        await client.get(
            f"/api/v1/projects/{project_id}",
            headers={"Authorization": f"Bearer {t2}"},
        )
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/projects/{project_id}",
            headers={"Authorization": f"Bearer {t2}"},
            json={"title": "Hijacked"},
        )
    ).status_code == 404
    assert (
        await client.delete(
            f"/api/v1/projects/{project_id}",
            headers={"Authorization": f"Bearer {t2}"},
        )
    ).status_code == 404

    # User 1 updates and archives, then deletes
    patch_res = await client.patch(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {t1}"},
        json={"title": "Updated AI Study", "is_archived": True},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Updated AI Study"
    assert patch_res.json()["is_archived"] is True

    del_res = await client.delete(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {t1}"},
    )
    assert del_res.status_code == 204
