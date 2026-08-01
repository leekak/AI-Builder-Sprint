from __future__ import annotations

from tests.conftest import complete_one_recall


def test_all_place_statuses_are_returned_in_one_request(client):
    response = client.get("/archive/places/statuses")
    assert response.status_code == 200, response.text
    statuses = response.json()
    assert len(statuses) == 50
    assert [item["place_tag"] for item in statuses] == sorted(item["place_tag"] for item in statuses)
    assert all(item["distinct_contributors"] == 0 for item in statuses)


def test_town_card_requires_distinct_contributors_and_uses_opt_in(client):
    cards = []
    details = [
        "비를 맞으며 우산 하나를 나눠 썼다",
        "첫 데이트 뒤 바닷가 벤치에 앉아 있었다",
        "가족과 밤바다를 보며 사진을 찍었다",
    ]
    for index, detail in enumerate(details, start=1):
        user = f"town-user-{index}"
        card = complete_one_recall(client, user=user, new_detail=detail)
        cards.append((user, card))
        shared = client.post(
            f"/cards/{card['id']}/share-to-town",
            headers={"X-User-Id": user},
            json={"consent": True, "place_tag": "광안리"},
        )
        assert shared.status_code == 200, shared.text

    status = client.get("/archive/places/광안리/status")
    assert status.status_code == 200
    assert status.json()["distinct_contributors"] == 3
    # 3번째 opt-in 공유 시점에 관리자 개입 없이 자동으로 카드가 생성되어, 더 만들 필요가 없어야 한다.
    assert status.json()["can_generate"] is False

    places = client.get("/archive/places").json()
    town_card = next(item for item in places if item["place"] == "광안리")
    assert town_card["contributors"] == 3
    assert town_card["place"] == "광안리"
    assert "바다 풍경" in town_card["story"]
    assert "비를 맞으며" not in town_card["story"]
    assert "비 오는 날 진우와 광안리에서 회를 먹고" not in town_card["story"]
    published_card = client.get(f"/cards/{cards[0][1]['id']}", headers={"X-User-Id": cards[0][0]})
    assert published_card.status_code == 200
    assert published_card.json()["town_share_status"] == "published"


def test_town_card_below_threshold_is_blocked(client):
    card = complete_one_recall(client, user="only-one")
    shared = client.post(
        f"/cards/{card['id']}/share-to-town",
        headers={"X-User-Id": "only-one"},
        json={"consent": True, "place_tag": "해운대"},
    )
    assert shared.status_code == 200
    response = client.post("/archive/places/해운대/card")
    assert response.status_code == 409


def test_town_share_preview_returns_the_sanitized_text_before_consent(client):
    user = "preview-user"
    card = complete_one_recall(client, user=user, new_detail="진우와 범죄도시를 보고 연어초밥을 먹었다")
    headers = {"X-User-Id": user}
    preview = client.post(
        f"/cards/{card['id']}/share-preview",
        headers=headers,
        json={"place_tag": "광안리"},
    )
    assert preview.status_code == 200, preview.text
    public_text = f"{preview.json()['safe_pre_text']} {preview.json()['safe_post_text']}"
    assert "진우" not in public_text
    assert "범죄도시" not in public_text
    assert "연어초밥" not in public_text
    assert client.get("/archive/places/광안리/status").json()["distinct_contributors"] == 0
    shared = client.post(
        f"/cards/{card['id']}/share-to-town",
        headers=headers,
        json={
            "consent": True,
            "place_tag": "광안리",
            "preview_token": preview.json()["preview_token"],
        },
    )
    assert shared.status_code == 200, shared.text
    assert client.get("/archive/places/광안리/status").json()["distinct_contributors"] == 1
    personal_card = client.get(f"/cards/{card['id']}", headers=headers)
    assert personal_card.json()["town_share_status"] == "pending"


def test_town_share_rejects_a_tampered_preview(client):
    user = "tampered-preview-user"
    card = complete_one_recall(client, user=user)
    response = client.post(
        f"/cards/{card['id']}/share-to-town",
        headers={"X-User-Id": user},
        json={"consent": True, "place_tag": "광안리", "preview_token": "invalid.token"},
    )
    assert response.status_code == 400


def test_town_card_same_contributions_cannot_be_generated_twice(client):
    for index in range(3):
        user = f"duplicate-user-{index}"
        card = complete_one_recall(client, user=user, new_detail=f"새 기억 {index}")
        assert client.post(
            f"/cards/{card['id']}/share-to-town",
            headers={"X-User-Id": user},
            json={"consent": True, "place_tag": "광안리"},
        ).status_code == 200

    # 3번째 공유 시점에 이미 자동으로 카드가 생성되어 있다.
    assert any(item["place"] == "광안리" for item in client.get("/archive/places").json())
    status = client.get("/archive/places/광안리/status").json()
    assert status["has_new_contributions"] is False
    assert status["new_contributors"] == 0
    assert status["can_generate"] is False
    duplicate = client.post("/archive/places/광안리/card")
    assert duplicate.status_code == 409
    assert "새로운 기여자" in duplicate.json()["detail"]["message"]


def test_town_card_is_updated_only_after_three_new_distinct_users(client):
    def contribute(user: str):
        card = complete_one_recall(client, user=user, new_detail=f"{user}의 바닷가 산책")
        response = client.post(
            f"/cards/{card['id']}/share-to-town",
            headers={"X-User-Id": user},
            json={"consent": True, "place_tag": "광안리"},
        )
        assert response.status_code == 200, response.text

    for user in ("initial-a", "initial-b", "initial-c"):
        contribute(user)
    # 3번째 공유 시점에 관리자 개입 없이 자동으로 첫 카드가 생성된다.
    first = next(item for item in client.get("/archive/places").json() if item["place"] == "광안리")
    assert first["version"] == 1

    for user in ("new-a", "new-b"):
        contribute(user)
    waiting = client.get("/archive/places/광안리/status").json()
    assert waiting["new_contributors"] == 2
    assert waiting["can_generate"] is False

    contribute("new-c")
    # 새 참여자 3명째(new-c) 공유 시점에 자동으로 같은 카드가 v2로 갱신된다.
    updated = next(item for item in client.get("/archive/places").json() if item["place"] == "광안리")
    assert updated["id"] == first["id"]
    assert updated["version"] == 2
    assert updated["contributors"] == 6
    assert len(client.get("/archive/places").json()) == 1

    ready = client.get("/archive/places/광안리/status").json()
    assert ready["new_contributors"] == 0
    assert ready["can_generate"] is False


def test_same_user_second_card_to_same_place_requires_explicit_replace(client):
    user = "one-heavy-user"
    first_card = complete_one_recall(client, user=user, new_detail="개인 기억 0")
    assert client.post(
        f"/cards/{first_card['id']}/share-to-town",
        headers={"X-User-Id": user},
        json={"consent": True, "place_tag": "광안리"},
    ).status_code == 200

    second_card = complete_one_recall(client, user=user, new_detail="개인 기억 1")
    conflict = client.post(
        f"/cards/{second_card['id']}/share-to-town",
        headers={"X-User-Id": user},
        json={"consent": True, "place_tag": "광안리"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["conflicting_card_id"] == first_card["id"]

    # 기존 조각은 그대로 남아있고, 아직 다른 사람 기여로 새로 잡히지 않는다.
    status = client.get("/archive/places/광안리/status").json()
    assert status["total_fragments"] == 1
    assert status["distinct_contributors"] == 1
    assert status["can_generate"] is False

    replaced = client.post(
        f"/cards/{second_card['id']}/share-to-town",
        headers={"X-User-Id": user},
        json={"consent": True, "place_tag": "광안리", "replace_existing": True},
    )
    assert replaced.status_code == 200, replaced.text

    status = client.get("/archive/places/광안리/status").json()
    assert status["total_fragments"] == 1
    assert status["distinct_contributors"] == 1

    old_card = client.get(f"/cards/{first_card['id']}", headers={"X-User-Id": user}).json()
    assert old_card["shared_to_town"] is False


def test_town_card_censors_profanity(client):
    from app.services.content_safety import contains_profanity

    for index, detail in enumerate(("씨발 바다가 보였다", "이런 shit 같은 날씨", "친구가 병신이라고 말했다")):
        user = f"profanity-user-{index}"
        card = complete_one_recall(client, user=user, new_detail=detail)
        assert client.post(
            f"/cards/{card['id']}/share-to-town",
            headers={"X-User-Id": user},
            json={"consent": True, "place_tag": "광안리"},
        ).status_code == 200
    generated = next(item for item in client.get("/archive/places").json() if item["place"] == "광안리")
    public_text = " ".join(generated[key] for key in ("card_title", "story", "reflection"))
    assert contains_profanity(public_text) is False


def test_unsharing_does_not_remove_memory_place(client):
    user = "place-owner"
    card = complete_one_recall(client, user=user, place_tag="광안리")
    headers = {"X-User-Id": user}
    assert client.post(
        f"/cards/{card['id']}/share-to-town",
        headers=headers,
        json={"consent": True, "place_tag": "해운대"},
    ).status_code == 200
    assert client.post(
        f"/cards/{card['id']}/share-to-town",
        headers=headers,
        json={"consent": False},
    ).status_code == 200
    memory = client.get(f"/memories/{card['memory_id']}", headers=headers).json()
    assert memory["place_tag"] == "광안리"
    assert memory["share_to_town"] is False


def test_town_card_removes_personal_names_groups_and_unique_events(client):
    details = [
        "진우랑 센텀에서 범죄도시를 보고 연어초밥을 먹었다",
        "디바 동아리 출사로 광안리에서 사진을 찍었다",
        "경제 인싸 3총사와 부산대로 이동해 온천천에서 맥주를 마셨다",
    ]
    for index, detail in enumerate(details):
        user = f"privacy-user-{index}"
        card = complete_one_recall(client, user=user, new_detail=detail)
        assert client.post(
            f"/cards/{card['id']}/share-to-town",
            headers={"X-User-Id": user},
            json={"consent": True, "place_tag": "광안리"},
        ).status_code == 200

    town_card = next(item for item in client.get("/archive/places").json() if item["place"] == "광안리")
    public_text = " ".join(
        town_card[field] for field in ("card_title", "story", "reflection")
    )
    for sensitive in ["진우", "디바", "3총사", "범죄도시", "연어초밥", "부산대", "온천천"]:
        assert sensitive not in public_text
