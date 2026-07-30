from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        auto_create_tables=True,
        storage_backend="local",
        local_storage_dir=str(tmp_path / "uploads"),
        ai_mode="mock",
        card_image_mode="mock",
        card_image_generation_enabled=True,
        demo_mode=True,
        demo_day_seconds=0,
        first_recall_days=0,
        second_recall_days=0,
        auth_mode="demo",
        town_min_contributors=3,
        admin_key=None,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def create_processed_memory(client, *, user="demo-user", comment="비 오는 날 진우와 광안리에서 회를 먹고 바닷가를 걸었다.", place_tag=None):
    headers = {"X-User-Id": user}
    response = client.post(
        "/memories",
        headers=headers,
        data={
            "comment": comment,
            "memory_date": "2026-07-20",
            "use_ocr": "false",
            "first_recall_days": "0",
            "second_recall_days": "0",
            **({"place_tag": place_tag} if place_tag else {}),
        },
    )
    assert response.status_code == 201, response.text
    memory = response.json()
    response = client.post(f"/memories/{memory['id']}/process", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["memory"]


def complete_one_recall(client, *, user="demo-user", comment=None, new_detail="우산 하나를 나눠 썼다", place_tag=None):
    memory = create_processed_memory(client, user=user, comment=comment or "비 오는 날 진우와 광안리에서 회를 먹고 바닷가를 걸었다.", place_tag=place_tag)
    headers = {"X-User-Id": user}
    response = client.post("/recalls", headers={**headers, "Content-Type": "application/json"}, json={"memory_id": memory["id"]})
    assert response.status_code == 201, response.text
    recall = response.json()
    response = client.post(f"/recalls/{recall['id']}/questions", headers=headers)
    assert response.status_code == 200, response.text
    response = client.post(
        f"/recalls/{recall['id']}/answers",
        headers={**headers, "Content-Type": "application/json"},
        json={"initial_answer": "친구와 바다에 갔던 기억이 난다", "hint_level": 0, "memory_not_recalled": False},
    )
    assert response.status_code == 200, response.text
    response = client.post(f"/recalls/{recall['id']}/reveal", headers=headers)
    assert response.status_code == 200, response.text
    response = client.post(
        f"/recalls/{recall['id']}/complete",
        headers={**headers, "Content-Type": "application/json"},
        json={"additional_memory": new_detail},
    )
    assert response.status_code == 200, response.text
    return response.json()
