from __future__ import annotations

import pytest


def test_image_is_truly_optional(client):
    response = client.post(
        "/memories",
        data={
            "comment": "이미지 없이 등록하는 기억",
            "memory_date": "2026-07-28",
            "use_ocr": "false",
            "first_recall_days": "0",
            "second_recall_days": "30",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["original_filename"] is None
    assert body["image_url"] is None
    assert body["ocr_status"] == "skipped"


def test_swagger_style_empty_image_string_is_coerced_to_none(client):
    response = client.post(
        "/memories",
        data={
            "comment": "Swagger 빈 이미지 필드 테스트",
            "memory_date": "2026-07-28",
            "use_ocr": "false",
            "first_recall_days": "0",
            "second_recall_days": "30",
        },
        files={"image": (None, "")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["image_url"] is None


def test_image_upload_and_private_read(client):
    image_bytes = b"\x89PNG\r\n\x1a\nnot-a-real-png-but-valid-for-storage-test"
    response = client.post(
        "/memories",
        data={
            "comment": "사진이 있는 기억",
            "memory_date": "2026-07-28",
            "use_ocr": "true",
            "first_recall_days": "0",
            "second_recall_days": "30",
        },
        files={"image": ("ticket.png", image_bytes, "image/png")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["image_url"]
    assert body["ocr_status"] == "pending"

    image_response = client.get(body["image_url"])
    assert image_response.status_code == 200
    assert image_response.content == image_bytes


def test_ocr_without_image_is_rejected(client):
    response = client.post(
        "/memories",
        data={
            "comment": "이미지 없는 OCR 요청",
            "memory_date": "2026-07-28",
            "use_ocr": "true",
            "first_recall_days": "0",
            "second_recall_days": "30",
        },
    )
    assert response.status_code == 400
    assert "OCR" in response.json()["detail"]


def test_place_tag_is_saved_from_registration(client):
    response = client.post(
        "/memories",
        data={
            "comment": "광안리에서 산책한 날",
            "memory_date": "2026-07-28",
            "use_ocr": "false",
            "place_tag": "광안리",
            "first_recall_days": "0",
            "second_recall_days": "30",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["place_tag"] == "광안리"
    assert response.json()["share_to_town"] is False


def test_unknown_place_tag_is_rejected(client):
    response = client.post(
        "/memories",
        data={
            "comment": "등록되지 않은 장소",
            "memory_date": "2026-07-28",
            "use_ocr": "false",
            "place_tag": "임의 장소",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "허용되지 않은 장소 태그입니다."


def test_free_form_place_is_preserved_and_standard_tag_is_recommended(client):
    response = client.post(
        "/memories",
        data={
            "comment": "친구와 커피를 마시며 바다를 봤다",
            "memory_date": "2026-07-28",
            "use_ocr": "false",
            "place_label": "광안리 해수욕장 앞 작은 카페",
            "first_recall_days": "0",
            "second_recall_days": "30",
        },
    )
    assert response.status_code == 201, response.text
    memory = response.json()
    assert memory["place_label"] == "광안리 해수욕장 앞 작은 카페"
    assert memory["place_tag"] is None

    processed = client.post(f"/memories/{memory['id']}/process")
    assert processed.status_code == 200, processed.text
    analyzed = processed.json()["memory"]
    assert analyzed["suggested_place_tag"] == "광안리"
    assert analyzed["place_tag"] is None

    confirmed = client.patch(f"/memories/{memory['id']}/place-tag", json={"place_tag": "광안리"})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["place_label"] == "광안리 해수욕장 앞 작은 카페"
    assert confirmed.json()["place_tag"] == "광안리"


def test_place_alias_is_mapped_to_a_broader_standard_tag(client):
    response = client.post(
        "/memories",
        data={
            "comment": "시장에서 먹거리를 구경했다",
            "memory_date": "2026-07-28",
            "use_ocr": "false",
            "place_label": "자갈치시장 입구",
            "first_recall_days": "0",
            "second_recall_days": "30",
        },
    )
    assert response.status_code == 201, response.text
    processed = client.post(f"/memories/{response.json()['id']}/process")
    assert processed.status_code == 200, processed.text
    assert processed.json()["memory"]["suggested_place_tag"] == "남포동"


def test_new_place_alias_is_mapped_to_its_standard_tag(client):
    response = client.post(
        "/memories",
        data={
            "comment": "카페에서 천천히 이야기를 나눴다",
            "memory_date": "2026-07-28",
            "use_ocr": "false",
            "place_label": "전포카페거리의 작은 카페",
            "first_recall_days": "0",
            "second_recall_days": "30",
        },
    )
    assert response.status_code == 201, response.text
    processed = client.post(f"/memories/{response.json()['id']}/process")
    assert processed.status_code == 200, processed.text
    assert processed.json()["memory"]["suggested_place_tag"] == "전포"


def test_due_memories_on_same_date_have_safe_distinguishers(client):
    from tests.conftest import create_processed_memory

    first = create_processed_memory(
        client,
        user="same-day-user",
        comment="진우와 광안리에서 산책했다",
        place_tag="광안리",
    )
    second = create_processed_memory(
        client,
        user="same-day-user",
        comment="가족과 해운대에서 저녁을 먹었다",
        place_tag="해운대",
    )

    response = client.get("/recalls/due", headers={"X-User-Id": "same-day-user"})
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    by_id = {item["memory_id"]: item for item in items}
    assert {by_id[first["id"]]["day_sequence"], by_id[second["id"]]["day_sequence"]} == {1, 2}
    assert by_id[first["id"]]["same_day_count"] == 2
    assert by_id[first["id"]]["place_tag"] == "광안리"
    assert by_id[second["id"]]["place_tag"] == "해운대"
    assert by_id[first["id"]]["cue_categories"]
    serialized = str(items)
    assert "진우와 광안리에서 산책했다" not in serialized
    assert "가족과 해운대에서 저녁을 먹었다" not in serialized
@pytest.mark.parametrize(
    ("first_days", "second_days"),
    [("31", "31"), ("7", "366")],
)
def test_recall_schedule_rejects_values_above_the_maximum(client, first_days, second_days):
    response = client.post(
        "/memories",
        data={
            "comment": "회상 가능일 상한 테스트",
            "memory_date": "2026-07-28",
            "use_ocr": "false",
            "first_recall_days": first_days,
            "second_recall_days": second_days,
        },
    )
    assert response.status_code == 422
