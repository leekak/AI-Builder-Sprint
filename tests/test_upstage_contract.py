from __future__ import annotations

import base64
import json

from app.config import Settings
from app.services.ai import UpstageAI


def test_information_extract_uses_current_json_contract(monkeypatch):
    settings = Settings(
        ai_mode="upstage",
        upstage_api_key="test-key",
        upstage_information_extract_url="https://example.test/information-extraction",
    )
    service = UpstageAI(settings)
    captured = {}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "people": ["진우"],
                                "places": ["광안리"],
                                "activities": ["산책"],
                                "atmosphere": ["비 오는 날"],
                                "emotions": [],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(service, "_post_json", fake_post)
    result = service.extract_context(text="비 오는 날 진우와 광안리에서 산책했다.")

    assert result["people"] == ["진우"]
    assert result["places"] == ["광안리"]
    assert captured["url"] == settings.upstage_information_extract_url
    body = captured["json"]
    assert body["model"] == "information-extract"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["name"] == "memory_context"
    data_url = body["messages"][0]["content"][0]["image_url"]["url"]
    assert data_url.startswith("data:image/png;base64,")
    image_bytes = base64.b64decode(data_url.split(",", 1)[1])
    assert image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
