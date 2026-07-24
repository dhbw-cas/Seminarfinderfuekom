from app import parse_recommendation_response, parse_seminars_from_catalog


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
