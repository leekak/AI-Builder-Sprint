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
                source_contribution_ids=["privacy:v3"],
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
        assert len(client.get("/archive/places").json()) == 1

        deleted = client.delete(
            "/archive/places/cards/town-card-for-admin-test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted"] is True
        assert client.get("/archive/places").json() == []

        deleted_cards = client.get(
            "/archive/places/cards/deleted",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert deleted_cards.status_code == 200, deleted_cards.text
        assert deleted_cards.json()[0]["id"] == "town-card-for-admin-test"
        assert deleted_cards.json()[0]["deleted_at"] is not None

        unauthorized_restore = client.post(
            "/archive/places/cards/town-card-for-admin-test/restore"
        )
        assert unauthorized_restore.status_code == 401

        restored = client.post(
            "/archive/places/cards/town-card-for-admin-test/restore",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["deleted_at"] is None
        assert len(client.get("/archive/places").json()) == 1
        assert client.get(
            "/archive/places/cards/deleted",
            headers={"Authorization": f"Bearer {token}"},
        ).json() == []


def test_restore_rejects_when_same_place_has_active_card(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'restore-conflict.db'}",
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
        now = datetime.now(timezone.utc)
        with app.state.SessionLocal() as db:
            db.add_all([
                TownCard(
                    id="deleted-card",
                    place_tag="광안리",
                    contributors=3,
                    card_title="삭제된 카드",
                    story="예전 이야기",
                    reflection="예전 성찰",
                    source_contribution_ids=["privacy:v3"],
                    published_contributor_keys=[],
                    version=1,
                    deleted_at=now,
                    deleted_by="admin",
                    created_at=now,
                    updated_at=now,
                ),
                TownCard(
                    id="active-card",
                    place_tag="광안리",
                    contributors=4,
                    card_title="현재 카드",
                    story="현재 이야기",
                    reflection="현재 성찰",
                    source_contribution_ids=["privacy:v3"],
                    published_contributor_keys=[],
                    version=2,
                    created_at=now,
                    updated_at=now,
                ),
            ])
            db.commit()

        login = client.post("/admin/login", json={"username": "admin", "password": "test-password"})
        token = login.json()["access_token"]
        restored = client.post(
            "/archive/places/cards/deleted-card/restore",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert restored.status_code == 409
        assert "이미 공개 중인 카드" in restored.json()["detail"]
