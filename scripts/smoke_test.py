from __future__ import annotations

import argparse
import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--user", default="smoke-user")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    headers = {"X-User-Id": args.user}
    with httpx.Client(timeout=60) as client:
        health = client.get(f"{base}/health")
        health.raise_for_status()
        print("health:", health.json()["status"])

        created = client.post(
            f"{base}/memories",
            headers=headers,
            data={
                "comment": "비 오는 날 친구와 광안리를 걸었다.",
                "memory_date": "2026-07-28",
                "use_ocr": "false",
                "first_recall_days": "0",
                "second_recall_days": "30",
            },
        )
        created.raise_for_status()
        memory = created.json()
        print("memory:", memory["id"])

        processed = client.post(f"{base}/memories/{memory['id']}/process", headers=headers)
        processed.raise_for_status()
        print("analysis:", processed.json()["memory"]["analysis"]["title"])

        recall = client.post(f"{base}/recalls", headers=headers, json={"memory_id": memory["id"]})
        recall.raise_for_status()
        recall_id = recall.json()["id"]
        client.post(f"{base}/recalls/{recall_id}/questions", headers=headers).raise_for_status()
        client.post(
            f"{base}/recalls/{recall_id}/answers",
            headers=headers,
            json={"initial_answer": "친구와 바다에 갔던 기억", "hint_level": 0},
        ).raise_for_status()
        client.post(f"{base}/recalls/{recall_id}/reveal", headers=headers).raise_for_status()
        completed = client.post(
            f"{base}/recalls/{recall_id}/complete",
            headers=headers,
            json={"additional_memory": "우산 하나를 나눠 썼다"},
        )
        completed.raise_for_status()
        print("card:", completed.json()["card_title"])
        print("smoke test: PASS")


if __name__ == "__main__":
    main()
