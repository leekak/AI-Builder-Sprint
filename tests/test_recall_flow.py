from __future__ import annotations

from tests.conftest import create_processed_memory


def test_complete_recall_flow_without_accuracy_score(client):
    memory = create_processed_memory(client)
    assert memory["analysis_status"] == "completed"
    assert memory["analysis"]["title"]
    assert "score" not in memory

    due = client.get("/recalls/due")
    assert due.status_code == 200, due.text
    assert any(item["memory_id"] == memory["id"] for item in due.json())
    assert all("comment" not in item and "image_url" not in item for item in due.json())

    created = client.post("/recalls", json={"memory_id": memory["id"]})
    assert created.status_code == 201, created.text
    recall_id = created.json()["id"]

    questions = client.post(f"/recalls/{recall_id}/questions")
    assert questions.status_code == 200, questions.text
    assert len(questions.json()["questions"]) == 3

    answer = client.post(
        f"/recalls/{recall_id}/answers",
        json={"initial_answer": "친구와 바다에 갔던 것 같다", "hint_level": 0},
    )
    assert answer.status_code == 200, answer.text

    reveal = client.post(f"/recalls/{recall_id}/reveal")
    assert reveal.status_code == 200, reveal.text
    assert reveal.json()["original_comment"].startswith("비 오는 날")

    additional = client.post(
        f"/recalls/{recall_id}/additional-memory",
        json={"text": "우산 하나를 나눠 썼고 비를 맞으며 걸었다"},
    )
    assert additional.status_code == 200, additional.text

    completed = client.post(f"/recalls/{recall_id}/complete", json={})
    assert completed.status_code == 200, completed.text
    card = completed.json()
    assert card["card_title"]
    assert "정답률" not in card["story"]
    assert "정확도" not in card["story"]
    assert card["newly_recalled_details"]

    cards = client.get("/cards")
    assert cards.status_code == 200
    assert cards.json()[0]["id"] == card["id"]


def test_hint_answers_can_be_saved_before_finalizing_recall(client):
    memory = create_processed_memory(client)
    created = client.post("/recalls", json={"memory_id": memory["id"]})
    recall_id = created.json()["id"]
    assert client.post(f"/recalls/{recall_id}/questions").status_code == 200

    first_hint = client.post(
        f"/recalls/{recall_id}/answers",
        json={"hint_answer": "비가 왔던 것 같다", "hint_level": 1, "finalize": False},
    )
    assert first_hint.status_code == 200, first_hint.text
    assert first_hint.json()["status"] == "question_ready"
    assert first_hint.json()["hint_level"] == 1

    revised_hint = client.post(
        f"/recalls/{recall_id}/answers",
        json={"hint_answer": "비가 오고 바람도 불었다", "hint_level": 1, "finalize": False},
    )
    assert revised_hint.status_code == 200, revised_hint.text
    assert len(revised_hint.json()["hint_answers"]) == 1
    assert revised_hint.json()["hint_answers"][0]["answer"] == "비가 오고 바람도 불었다"

    finalized = client.post(
        f"/recalls/{recall_id}/answers",
        json={"hint_answer": "누군가와 걸었다", "hint_level": 2, "finalize": True},
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "answered"
    assert len(finalized.json()["hint_answers"]) == 2
    assert client.post(f"/recalls/{recall_id}/reveal").status_code == 200


def test_owner_isolation(client):
    memory = create_processed_memory(client, user="user-a")
    response = client.get(f"/memories/{memory['id']}", headers={"X-User-Id": "user-b"})
    assert response.status_code == 404


def test_second_recall_updates_the_same_memory_card(client):
    memory = create_processed_memory(client)

    def complete_stage(initial_answer, additional_memory):
        created = client.post("/recalls", json={"memory_id": memory["id"]})
        assert created.status_code == 201, created.text
        recall_id = created.json()["id"]
        assert client.post(f"/recalls/{recall_id}/questions").status_code == 200
        answered = client.post(
            f"/recalls/{recall_id}/answers",
            json={
                "initial_answer": initial_answer,
                "hint_level": 0,
                "memory_not_recalled": False,
            },
        )
        assert answered.status_code == 200, answered.text
        assert client.post(f"/recalls/{recall_id}/reveal").status_code == 200
        completed = client.post(
            f"/recalls/{recall_id}/complete",
            json={"additional_memory": additional_memory},
        )
        assert completed.status_code == 200, completed.text
        return completed.json()

    first_card = complete_stage("친구와 바다에 갔다", "우산을 나눠 썼다")
    second_card = complete_stage("비 오는 광안리를 걸었다", "바다 냄새도 떠올랐다")

    assert second_card["id"] == first_card["id"]
    assert second_card["recall_id"] != first_card["recall_id"]
    cards = client.get("/cards")
    assert cards.status_code == 200
    assert len(cards.json()) == 1
    assert "1차 회상" in second_card["story"]
    assert "2차 회상" in second_card["story"]
    assert [item["stage"] for item in second_card["recall_history"]] == [1, 2]
    assert second_card["updated_at"] >= second_card["created_at"]
    assert second_card["latest_recall_added_count"] == 1
