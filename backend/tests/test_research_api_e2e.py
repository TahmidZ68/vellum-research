import asyncio

import pytest
from httpx import AsyncClient

from app.core.config import get_settings


@pytest.mark.asyncio
async def test_missing_api_keys_returns_clear_setup_guidance(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "keys@example.com", "password": "StrongPassword123!"},
    )
    token = reg.json()["access_token"]

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS", "false")
    get_settings.cache_clear()

    res = await client.post(
        "/api/v1/research",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "Compare open-source AI agent frameworks", "depth": "quick"},
    )
    assert res.status_code == 503
    assert "GEMINI_API_KEY" in res.json()["detail"]


@pytest.mark.asyncio
async def test_end_to_end_research_run_report_followup_exports_and_ownership(
    client: AsyncClient,
) -> None:
    u1 = await client.post(
        "/api/v1/auth/register",
        json={"email": "researcher@example.com", "password": "StrongPassword123!"},
    )
    u2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "StrongPassword123!"},
    )
    t1 = u1.json()["access_token"]
    t2 = u2.json()["access_token"]

    start_res = await client.post(
        "/api/v1/research",
        headers={"Authorization": f"Bearer {t1}"},
        json={
            "query": "Research the current AI automation market in Bangladesh",
            "context": "Focus on services, pricing models, and opportunities",
            "depth": "quick",
            "language": "en",
        },
    )
    assert start_res.status_code == 201, start_res.text
    run_id = start_res.json()["id"]
    assert start_res.json()["is_demo_mode"] is True

    # Poll until inline background task completes
    final_status = None
    for _ in range(60):
        status_res = await client.get(
            f"/api/v1/research/{run_id}",
            headers={"Authorization": f"Bearer {t1}"},
        )
        assert status_res.status_code == 200
        body = status_res.json()
        if body["status"] in {"completed", "failed", "cancelled"}:
            final_status = body
            break
        await asyncio.sleep(0.1)

    assert final_status is not None
    assert final_status["status"] == "completed", final_status
    assert final_status["has_report"] is True
    assert final_status["source_count"] >= 1
    assert final_status["evidence_count"] >= 1

    # Sources & Evidence endpoints
    sources_res = await client.get(
        f"/api/v1/research/{run_id}/sources",
        headers={"Authorization": f"Bearer {t1}"},
    )
    assert sources_res.status_code == 200
    assert len(sources_res.json()) >= 1

    # Report endpoint with validated citations
    report_res = await client.get(
        f"/api/v1/research/{run_id}/report",
        headers={"Authorization": f"Bearer {t1}"},
    )
    assert report_res.status_code == 200
    report = report_res.json()
    assert report["status"] == "validated"
    assert report["citation_validation"]["is_valid"] is True
    assert len(report["citations"]) >= 1
    assert "## References" in report["content"]

    # Follow-up question
    follow_res = await client.post(
        f"/api/v1/research/{run_id}/follow-up",
        headers={"Authorization": f"Bearer {t1}"},
        json={"question": "What pricing models were observed?"},
    )
    assert follow_res.status_code == 200
    assert follow_res.json()["assistant_message"]["content"]

    # Markdown & PDF exports
    md_export = await client.get(
        f"/api/v1/research/{run_id}/export?format=markdown",
        headers={"Authorization": f"Bearer {t1}"},
    )
    assert md_export.status_code == 200
    assert "text/markdown" in md_export.headers["content-type"]
    assert "## References" in md_export.text

    pdf_export = await client.get(
        f"/api/v1/research/{run_id}/export?format=pdf",
        headers={"Authorization": f"Bearer {t1}"},
    )
    assert pdf_export.status_code == 200
    assert pdf_export.headers["content-type"] == "application/pdf"
    assert pdf_export.content.startswith(b"%PDF")

    # Ownership enforcement across all research endpoints for User 2
    for path in (
        f"/api/v1/research/{run_id}",
        f"/api/v1/research/{run_id}/sources",
        f"/api/v1/research/{run_id}/evidence",
        f"/api/v1/research/{run_id}/report",
        f"/api/v1/research/{run_id}/export?format=markdown",
    ):
        denied = await client.get(path, headers={"Authorization": f"Bearer {t2}"})
        assert denied.status_code == 404
