from __future__ import annotations

from sqlalchemy import select

from app.models import TownArchivedFragment, TownContribution
from tests.conftest import complete_one_recall


def _share(client, user: str, card: dict, place: str = "광안리"):
    response = client.post(
        f"/cards/{card['id']}/share-to-town",
        headers={"X-User-Id": user},
        json={"consent": True, "place_tag": place},
    )
    assert response.status_code == 200, response.text


def test_delete_memory_removes_unpublished_contribution(client):
    user = "delete-before-publish"
    card = complete_one_recall(client, user=user, new_detail="진우와 공연을 본 뒤 식사했다")
    _share(client, user, card)

    response = client.delete(f"/memories/{card['memory_id']}", headers={"X-User-Id": user})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["removed_pending_contributions"] == 1
    assert result["preserved_anonymous_fragments"] == 0
    assert client.get(f"/memories/{card['memory_id']}", headers={"X-User-Id": user}).status_code == 404
    assert client.get(f"/cards/{card['id']}", headers={"X-User-Id": user}).status_code == 404

    with client.app.state.SessionLocal() as db:
        assert db.scalars(select(TownContribution)).all() == []
        assert db.scalars(select(TownArchivedFragment)).all() == []


def test_delete_memory_preserves_only_anonymous_fragment_after_publish(client):
    cards = []
    for index, detail in enumerate([
        "진우와 범죄도시를 보고 연어초밥을 먹었다",
        "친구와 바다를 걸으며 사진을 찍었다",
        "가족과 비 오는 해변을 산책했다",
    ]):
        user = f"published-user-{index}"
        card = complete_one_recall(client, user=user, new_detail=detail)
        _share(client, user, card)
        cards.append((user, card))

    generated = client.post("/archive/places/광안리/card")
    assert generated.status_code == 201, generated.text
    town_card_id = generated.json()["id"]

    user, card = cards[0]
    deleted = client.delete(f"/memories/{card['memory_id']}", headers={"X-User-Id": user})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["preserved_anonymous_fragments"] == 1
    assert client.get(f"/memories/{card['memory_id']}", headers={"X-User-Id": user}).status_code == 404

    public_cards = client.get("/archive/places").json()
    assert any(item["id"] == town_card_id for item in public_cards)
    status = client.get("/archive/places/광안리/status").json()
    assert status["distinct_contributors"] == 3
    assert status["has_new_contributions"] is False

    with client.app.state.SessionLocal() as db:
        archived = db.scalars(select(TownArchivedFragment)).all()
        assert len(archived) == 1
        safe_text = f"{archived[0].pre_reveal_text} {archived[0].post_reveal_text}"
        for private_term in ["진우", "범죄도시", "연어초밥"]:
            assert private_term not in safe_text
        assert not hasattr(archived[0], "owner_id")
