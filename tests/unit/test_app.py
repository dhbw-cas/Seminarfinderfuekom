import json
from pathlib import Path
from typing import Any

import pytest

from app import (
    _read_positive_int_env,
    build_system_prompt,
    llm_chat_openai_compatible,
    load_course_knowledge_from_file,
    parse_recommendation_response,
    parse_seminars_from_catalog,
)


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"choices": [{"message": {"content": '{"short_answer":"ok"}'}}]}


def test_load_course_knowledge_from_file_rejects_empty_file(tmp_path: Path) -> None:
    knowledge_file = tmp_path / "course.md"
    knowledge_file.write_text("Testat und Modulablauf", encoding="utf-8")

    assert (
        load_course_knowledge_from_file(
            str(knowledge_file), knowledge_file.stat().st_mtime
        )
        == "Testat und Modulablauf"
    )

    empty_file = tmp_path / "empty.md"
    empty_file.write_text("  \n", encoding="utf-8")

    with pytest.raises(ValueError, match="Kurswissensdatei ist leer"):
        load_course_knowledge_from_file(str(empty_file), empty_file.stat().st_mtime)


def test_parse_seminars_from_catalog_extracts_required_fields() -> None:
    catalog = """
### Selbstführung & Resilienz

#### Resilienz stärken
**Fokus:** Stress und Resilienz
**Inhalte:** Achtsamkeit und Regeneration
**Voraussetzungen:** Keine
**Dualis:** ABC123.4.5
"""

    seminars = parse_seminars_from_catalog(catalog)

    assert len(seminars) == 1
    seminar = seminars[0]
    assert seminar.seminar_id == "resilienz-starken"
    assert seminar.title == "Resilienz stärken"
    assert seminar.category == "Selbstführung & Resilienz"
    assert seminar.dualis_code == "ABC123.4.5"


def test_parse_recommendation_response_keeps_only_known_seminar_ids() -> None:
    seminars = parse_seminars_from_catalog(
        """
### Kommunikation

#### Sicher präsentieren
**Fokus:** Auftritt und Rhetorik
"""
    )
    raw_response = """{
        "short_answer": "Das passt gut.",
        "recommended_ids": ["sicher-prasentieren", "unbekannt"],
        "why": {"sicher-prasentieren": "Trifft den Wunsch nach Auftrittssicherheit."}
    }"""

    answer, recommended_ids, reasons = parse_recommendation_response(
        raw_text=raw_response,
        seminars=seminars,
        user_prompt="Ich möchte besser präsentieren.",
        top_n=3,
    )

    assert answer == "Das passt gut."
    assert recommended_ids == ["sicher-prasentieren"]
    assert reasons == {
        "sicher-prasentieren": "Trifft den Wunsch nach Auftrittssicherheit."
    }


def test_parse_recommendation_response_respects_explicit_empty_ids() -> None:
    seminars = parse_seminars_from_catalog(
        """
### Kommunikation

#### Sicher präsentieren
**Fokus:** Auftritt und Rhetorik
"""
    )
    raw_response = """{
        "short_answer": "Für das Testat brauchst du alle Pflichtbestandteile.",
        "recommended_ids": [],
        "why": {}
    }"""

    answer, recommended_ids, reasons = parse_recommendation_response(
        raw_text=raw_response,
        seminars=seminars,
        user_prompt="Welches Seminar brauche ich für das Testat?",
        top_n=3,
    )

    assert answer == "Für das Testat brauchst du alle Pflichtbestandteile."
    assert recommended_ids == []
    assert reasons == {}


def test_build_system_prompt_contains_strict_json_and_clarification_rules() -> None:
    catalog = """
### Kommunikation

#### Sicher präsentieren
**Fokus:** Auftritt und Rhetorik
"""
    seminars = parse_seminars_from_catalog(catalog)

    course_knowledge = "Das Testat umfasst 5 ECTS-Leistungspunkte."
    prompt = build_system_prompt(
        catalog_text=catalog,
        course_knowledge=course_knowledge,
        seminars=seminars,
        top_n=2,
    )

    assert "genau eine gezielte Rückfrage" in prompt
    assert "gib keine Seminar-IDs aus" in prompt
    assert "Kein Markdown, keine Code-Fences" in prompt
    assert '"recommended_ids": Liste mit maximal 2 Seminar-IDs' in prompt
    assert "Weniger als 2 Empfehlungen sind erlaubt" in prompt
    assert "Dualis für Modul und Veranstaltung" in prompt
    assert course_knowledge in prompt
    assert "digitale FüKom-Kurs- und Seminarberater" in prompt
    assert "Modulaufbau, Testat, ECTS, Anmeldung" in prompt
    assert "eine leere Liste recommended_ids" in prompt
    assert "keinen Zugriff auf persönliche Moodle- oder Dualis-Daten" in prompt
    assert "maximal 8 Sätze" in prompt
    assert "(Quelle: Prüfungsleistung und Abschluss)" in prompt
    assert "Frage: Wie melde ich mich zu einem Seminar an?" in prompt
    assert "<kurswissen>" in prompt
    assert "<seminar_katalog>" in prompt


def test_llm_chat_openai_compatible_sends_openai_compatible_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_post(
        endpoint: str,
        headers: dict[str, str],
        data: str,
        timeout: int,
        stream: bool = False,
    ) -> FakeResponse:
        captured["endpoint"] = endpoint
        captured["headers"] = headers
        captured["payload"] = json.loads(data)
        captured["timeout"] = timeout
        captured["stream"] = stream
        return FakeResponse()

    monkeypatch.setattr("app.requests.post", fake_post)

    answer = llm_chat_openai_compatible(
        api_key="test-token",
        model="mistral/mistral-small-3.2-24b-instruct-2506:fp8",
        endpoint="https://api.scaleway.ai/v1/chat/completions",
        system_prompt="Antworte als JSON.",
        history=[{"role": "user", "content": "Hallo"}],
        stream=False,
        max_tokens=1000,
    )

    assert answer == '{"short_answer":"ok"}'
    assert captured["endpoint"] == "https://api.scaleway.ai/v1/chat/completions"
    assert captured["headers"] == {
        "Authorization": "Bearer test-token",
        "Content-Type": "application/json",
    }
    assert captured["payload"] == {
        "model": "mistral/mistral-small-3.2-24b-instruct-2506:fp8",
        "messages": [
            {"role": "system", "content": "Antworte als JSON."},
            {"role": "user", "content": "Hallo"},
        ],
        "temperature": 0.2,
        "stream": False,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"},
    }
    assert captured["timeout"] == 120
    assert captured["stream"] is False


def test_read_positive_int_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    assert _read_positive_int_env("LLM_MAX_TOKENS", 1000) == 1000

    monkeypatch.setenv("LLM_MAX_TOKENS", "1200")
    assert _read_positive_int_env("LLM_MAX_TOKENS", 1000) == 1200

    monkeypatch.setenv("LLM_MAX_TOKENS", "0")
    with pytest.raises(ValueError, match="größer als 0"):
        _read_positive_int_env("LLM_MAX_TOKENS", 1000)
