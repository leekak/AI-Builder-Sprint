from __future__ import annotations

import io

from PIL import Image

from app.models import Memory, MemoryCard
from tests.conftest import complete_one_recall


def test_text_card_image_generation_and_removal(client):
    card = complete_one_recall(client, user="image-user")
    headers = {"X-User-Id": "image-user"}

    generated = client.post(
        f"/cards/{card['id']}/generate-image",
        headers=headers,
        json={"mode": "text_illustration"},
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["status"] == "completed"
    assert generated.json()["generated_image_url"]

    image = client.get(generated.json()["generated_image_url"], headers=headers)
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")
    assert image.content.startswith(b"\x89PNG")

    other_user = client.get(generated.json()["generated_image_url"], headers={"X-User-Id": "other-user"})
    assert other_user.status_code == 404

    removed = client.delete(f"/cards/{card['id']}/generated-image", headers=headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "not_requested"
    assert removed.json()["generated_image_url"] is None


def test_original_photo_card_rejects_generated_image(client):
    card = complete_one_recall(client, user="photo-user")
    output = io.BytesIO()
    Image.new("RGB", (40, 30), (220, 210, 190)).save(output, format="PNG")
    stored = client.app.state.storage.save(
        owner_id="photo-user",
        filename="memory.png",
        content_type="image/png",
        data=output.getvalue(),
    )
    with client.app.state.SessionLocal() as db:
        memory = db.get(Memory, card["memory_id"])
        memory.image_path = stored.path
        memory.image_filename = stored.filename
        memory.image_content_type = stored.content_type
        db.commit()

    response = client.post(
        f"/cards/{card['id']}/generate-image",
        headers={"X-User-Id": "photo-user"},
        json={"mode": "text_illustration"},
    )
    assert response.status_code == 409
    assert "원본 사진" in response.text


def test_image_style_is_selected_automatically(client):
    card = complete_one_recall(client, user="auto-style-user")
    response = client.post(
        f"/cards/{card['id']}/generate-image",
        headers={"X-User-Id": "auto-style-user"},
        json={"mode": "text_illustration"},
    )
    assert response.status_code == 200, response.text
    with client.app.state.SessionLocal() as db:
        saved = db.get(MemoryCard, card["id"])
        assert saved.image_generation_style == "soft_film"
