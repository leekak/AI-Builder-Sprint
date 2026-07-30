from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import TownCard


def test_only_logged_in_admin_can_delete_town_card(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'admin.db'}",
        auto_create_tables=True,
        storage_backend="local",
        local_storage_dir=str(tmp_path / "uploads"),
        ai_mode="mock",
        auth_mode="demo",
        admin_username="admin",
        admin_password="test-password",
        admin_token_secret="test-admin-token-secret-that-is-long-enough",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        with app.state.SessionLocal() as db:
            db.add(TownCard(
                id="town-card-for-admin-test",
                place_tag="광안리",
                contributors=3,
                card_title="광안리 추억 카드",
                story="여럿의 기억이 모인 이야기",
                reflection="장소는 기억으로 이어집니다.",
                source_contribution_ids=["privacy-pipeline:v1"],
                published_contributor_keys=[],
                version=1,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
            db.commit()

        unauthorized = client.delete("/archive/places/cards/town-card-for-admin-test")
        assert unauthorized.status_code == 401

        wrong = client.post("/admin/login", json={"username": "admin", "password": "wrong"})
        assert wrong.status_code == 401

        login = client.post("/admin/login", json={"username": "admin", "password": "test-password"})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        me = client.get("/admin/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["role"] == "admin"

        deleted = client.delete(
            "/archive/places/cards/town-card-for-admin-test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted"] is True
        assert client.get("/archive/places").json() == []
