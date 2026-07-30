from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_demo_ui_uses_modular_frontend(client):
    response = client.get("/demo/")
    assert response.status_code == 200
    html = response.text
    assert 'name="place_label"' in html
    assert 'id="placeLabel"' in html
    assert 'id="shareAfterComplete"' in html
    assert 'id="placeTagsList"' in html
    assert 'id="recallPlace" list="placeTagsList"' in html
    assert 'id="townPlace" list="placeTagsList"' in html
    assert 'id="demoPreset"' in html
    assert 'id="revealOriginal" class="secondary" disabled' in html
    assert 'id="recallActionGuide"' in html
    assert 'class="skip-link"' not in html
    assert 'type="module" src="/demo/js/main.js"' in html


def test_tab_changes_clear_transient_register_and_recall_ui():
    with open("app/static/js/main.js", encoding="utf-8") as source:
        main_js = source.read()
    with open("app/static/js/recall.js", encoding="utf-8") as source:
        recall_js = source.read()

    assert "if (event.detail !== 'register') clearRegisterResult();" in main_js
    assert "if (event.detail !== 'recall') closeRecallWorkspace();" in main_js
    assert "export function closeRecallWorkspace()" in recall_js
    assert "saveDraft();" in recall_js
    assert "workspace.classList.add('hidden');" in recall_js

    expected_modules = {"api.js", "register.js", "recall.js", "cards.js", "town.js", "privacy.js", "utils.js", "main.js"}
    assert expected_modules.issubset({path.name for path in (STATIC / "js").glob("*.js")})


def test_demo_assets_are_served(client):
    assert client.get("/demo/styles.css").status_code == 200
    assert client.get("/demo/js/main.js").status_code == 200
    assert client.get("/demo/js/api.js").status_code == 200


def test_recall_ui_enforces_answer_before_reveal(client):
    script = client.get("/demo/js/recall.js").text
    assert "setRecallStage('saved')" in script
    assert "reveal.disabled = true" in script
    assert "reveal.disabled = false" in script
    assert "$('#initialAnswer').disabled = true" in script
    assert "기존 추억 카드에 반영하기" in script
    assert "카드에 이번 회상을 반영했습니다" in script
    assert "recall-draft:" in script
    assert "localStorage.setItem" in script
