#!/usr/bin/env python3

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import requests
import streamlit as st

DEFAULT_CATALOG_FILE = "data/catalog.md"
DEFAULT_LLM_ENDPOINT = "https://api.scaleway.ai/v1/chat/completions"
DEFAULT_LLM_MODEL = "mistral/mistral-small-3.2-24b-instruct-2506:fp8"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_RESULT_COUNT = 3
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Selbstführung & Resilienz": [
        "stress",
        "resilienz",
        "burnout",
        "achtsamkeit",
        "mindfulness",
        "regeneration",
        "selbstführung",
        "zeitmanagement",
        "entscheidung",
    ],
    "Karriere & Persönlichkeit": [
        "karriere",
        "laufbahn",
        "beförderung",
        "entwicklung",
        "sichtbar",
        "persönlichkeit",
        "selbstvertrauen",
        "ausstrahlung",
        "glücklich",
    ],
    "Auftritt & Kommunikation": [
        "kommunikation",
        "gespräch",
        "rhetorik",
        "präsent",
        "stimme",
        "charisma",
        "auftritt",
        "visual",
    ],
    "Konflikt & Verhandlung": [
        "konflikt",
        "verhand",
        "einwand",
        "metakommunikation",
        "moderation",
        "anspruchsvollen situationen",
    ],
    "Führung & Team": [
        "führung",
        "team",
        "leadership",
        "change",
        "coaching",
        "diversity",
        "laterale",
        "motivation",
    ],
    "Interkulturell & Englisch": [
        "südostasien",
        "china",
        "japan",
        "korea",
        "singapur",
        "malaysia",
        "inclusive teamwork",
        "englisch",
        "interkulturell",
    ],
    "KI & Digitalisierung": [
        "ki-kompetenz",
        "prompting",
        "künstliche intelligenz",
        "digitalisierung",
        "simulation",
    ],
}


@dataclass(frozen=True)
class Seminar:
    seminar_id: str
    title: str
    category: str
    focus: str
    content: str
    methods: str
    requirements: str
    dualis_code: str
    raw_markdown: str


def catalog_mtime(file_path: str) -> float:
    return Path(file_path).stat().st_mtime


@st.cache_data(show_spinner=False)
def load_catalog_from_file(file_path: str, file_mtime: float) -> str:
    del file_mtime
    catalog_text = Path(file_path).read_text(encoding="utf-8")
    if not catalog_text.strip():
        raise ValueError("Katalogdatei ist leer.")
    return catalog_text


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "seminar"


def _collect_field_values(block_lines: list[str], keywords: list[str]) -> str:
    sections: dict[str, list[str]] = {}
    current_key = ""

    for raw_line in block_lines:
        line = raw_line.strip()
        match = re.match(r"^\*\*(.+?):\*\*\s*(.*)$", line)
        if match:
            current_key = match.group(1).strip().lower()
            first_content = match.group(2).strip()
            if first_content:
                sections.setdefault(current_key, []).append(first_content)
            continue

        if current_key and line:
            sections.setdefault(current_key, []).append(line)

    collected_parts: list[str] = []
    for key, values in sections.items():
        if any(keyword in key for keyword in keywords):
            collected_parts.extend(values)

    return "\n".join(collected_parts).strip()


def _normalize_dualis_code(raw_value: str) -> str:
    if not raw_value:
        return ""
    first_line = raw_value.splitlines()[0].strip()
    match = re.search(r"[A-Z]{3}\d+(?:\.\d+)+", first_line)
    return match.group(0) if match else first_line


def _read_positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} muss eine ganze Zahl sein.") from exc

    if value < 1:
        raise ValueError(f"{name} muss größer als 0 sein.")
    return value


@st.cache_data(show_spinner=False)
def parse_seminars_from_catalog(catalog_text: str) -> list[Seminar]:
    seminars: list[Seminar] = []
    used_ids: dict[str, int] = {}
    current_category = ""
    current_title = ""
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_title, current_lines
        if not current_title:
            return

        base_slug = _slugify(current_title)
        used_ids[base_slug] = used_ids.get(base_slug, 0) + 1
        seminar_id = (
            base_slug
            if used_ids[base_slug] == 1
            else f"{base_slug}-{used_ids[base_slug]}"
        )

        focus = _collect_field_values(current_lines, ["fokus", "profil", "ziele"])
        content = _collect_field_values(current_lines, ["inhalte", "inhalt", "setting"])
        methods = _collect_field_values(current_lines, ["methoden"])
        requirements = _collect_field_values(
            current_lines, ["voraussetzungen", "besonderheiten"]
        )
        dualis_code = _normalize_dualis_code(
            _collect_field_values(current_lines, ["dualis"])
        )
        raw_markdown = "\n".join(current_lines).strip()
        if not focus:
            first_line = next(
                (line.strip() for line in current_lines if line.strip()), ""
            )
            focus = first_line

        seminars.append(
            Seminar(
                seminar_id=seminar_id,
                title=current_title,
                category=current_category or "Ohne Kategorie",
                focus=focus,
                content=content,
                methods=methods,
                requirements=requirements,
                dualis_code=dualis_code,
                raw_markdown=raw_markdown,
            )
        )
        current_title = ""
        current_lines = []

    for line in catalog_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            flush_current()
            current_category = stripped[4:].strip()
            continue

        if stripped.startswith("#### "):
            flush_current()
            current_title = stripped[5:].strip()
            current_lines = []
            continue

        if current_title:
            current_lines.append(line)

    flush_current()
    return seminars


def build_seminar_reference(seminars: list[Seminar]) -> str:
    lines = []
    for seminar in seminars:
        focus = seminar.focus.replace("\n", " ").strip()
        requirements = seminar.requirements.replace("\n", " ").strip()
        lines.append(
            f"- id={seminar.seminar_id} | titel={seminar.title} | kategorie={seminar.category} | "
            f"fokus={focus[:240]} | voraussetzungen={requirements[:160]}"
        )
    return "\n".join(lines)


def _extract_first_json_object(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL
        ).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return {}


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-ZäöüÄÖÜß]{3,}", text.lower())]


def seminar_topics(seminar: Seminar) -> list[str]:
    searchable = (
        f"{seminar.title} {seminar.category} {seminar.focus} {seminar.content}".lower()
    )
    topics = [
        topic
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(keyword in searchable for keyword in keywords)
    ]
    return topics


def _fallback_recommendations(
    user_prompt: str, seminars: list[Seminar], top_n: int
) -> list[str]:
    query_tokens = _tokenize(user_prompt)
    if not query_tokens:
        return []

    scored: list[tuple[int, str]] = []
    for seminar in seminars:
        searchable = (
            f"{seminar.title} {seminar.category} {seminar.focus} "
            f"{seminar.content} {seminar.requirements}"
        ).lower()
        score = sum(searchable.count(token) for token in query_tokens)
        if score > 0:
            scored.append((score, seminar.seminar_id))

    scored.sort(reverse=True)
    return [seminar_id for _, seminar_id in scored[:top_n]]


def parse_recommendation_response(
    raw_text: str, seminars: list[Seminar], user_prompt: str, top_n: int
) -> tuple[str, list[str], dict[str, str]]:
    parsed = _extract_first_json_object(raw_text)
    valid_ids = {seminar.seminar_id for seminar in seminars}
    recommended_ids: list[str] = []

    candidate_ids = parsed.get("recommended_ids", [])
    if isinstance(candidate_ids, list):
        for item in candidate_ids:
            if (
                isinstance(item, str)
                and item in valid_ids
                and item not in recommended_ids
            ):
                recommended_ids.append(item)
            if len(recommended_ids) >= top_n:
                break

    if not recommended_ids:
        recommended_ids = _fallback_recommendations(
            user_prompt=user_prompt, seminars=seminars, top_n=top_n
        )

    short_answer = (
        parsed.get("short_answer", "").strip()
        if isinstance(parsed.get("short_answer"), str)
        else ""
    )
    if not short_answer:
        if recommended_ids:
            short_answer = "Ich habe drei passende Seminare herausgesucht. Du findest sie unten als Karten."
        else:
            short_answer = (
                "Ich habe dazu noch keine klar passenden Seminare gefunden. "
                "Nenne mir bitte Thema, Ziel oder bevorzugtes Format."
            )

    reasons_raw = parsed.get("why", {})
    reasons: dict[str, str] = {}
    if isinstance(reasons_raw, dict):
        for seminar_id, reason in reasons_raw.items():
            if seminar_id in valid_ids and isinstance(reason, str):
                reasons[seminar_id] = reason.strip()

    return short_answer, recommended_ids, reasons


def build_system_prompt(catalog_text: str, seminars: list[Seminar], top_n: int) -> str:
    seminar_reference = build_seminar_reference(seminars)
    return (
        "Du bist ein Studienberater für Seminare. "
        "Deine Aufgabe ist, Studierende bei der Auswahl passender Seminare zu unterstützen.\n\n"
        "Regeln:\n"
        "1) Antworte auf Deutsch, klar und freundlich.\n"
        "2) Verwende ausschließlich Informationen aus dem bereitgestellten Katalog.\n"
        "3) Wenn Informationen fehlen, sage das transparent.\n"
        "4) Stelle bei Bedarf gezielte Rückfragen (Interessen, Vorkenntnisse, Zeit, Sprache, Prüfungsform). Stelle auch erst Rückfragen, wenn der Besucher noch keine Vorstellung hat, was er brauchen könnte.\n"
        "5) Gib konkrete Empfehlungen mit kurzer Begründung.\n"
        "6) Antworte ausschließlich als JSON-Objekt mit den Feldern:\n"
        '   - "short_answer": kurzer Text (max. 3-5 Sätze)\n'
        f'   - "recommended_ids": Liste mit maximal {top_n} Seminar-IDs aus der Referenzliste\n'
        '   - "why": Objekt mit optionalen Kurzbegründungen je Seminar-ID\n'
        "7) Gib keine IDs aus, die nicht in der Referenzliste stehen.\n\n"
        "8) Wenn Du Seminare vorgeschlagen hast, erinnere den Studenten daran, sich in Dualis auf das Modul und die Veranstaltung anzumelden.\n\n"
        "SEMINAR-REFERENZLISTE:\n"
        f"{seminar_reference}\n\n"
        "KATALOG (Wissensbasis):\n"
        f"{catalog_text[:120000]}"
    )


def _extract_non_stream_response(payload: dict) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return "Ich konnte keine Antwort vom Modell erhalten. Bitte versuche es erneut."
    message = choices[0].get("message", {})
    return message.get("content", "") or "Ich konnte keine Antwort vom Modell erhalten."


def _extract_stream_response(response: requests.Response) -> str:
    chunks: list[str] = []
    for line in response.iter_lines():
        if not line:
            continue

        decoded = line.decode("utf-8")
        if not decoded.startswith("data: "):
            continue

        data_part = decoded[6:]
        if data_part == "[DONE]":
            break

        try:
            chunk_json = json.loads(data_part)
        except json.JSONDecodeError:
            continue

        delta = chunk_json.get("choices", [{}])[0].get("delta", {})
        token = delta.get("content")
        if token:
            chunks.append(token)

    return "".join(chunks).strip() or "Ich konnte keine Antwort vom Modell erhalten."


def llm_chat_openai_compatible(
    api_key: str,
    model: str,
    endpoint: str,
    system_prompt: str,
    history: list[dict[str, str]],
    stream: bool,
    max_tokens: int,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *history],
        "temperature": 0.2,
        "stream": stream,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    if stream:
        response = requests.post(
            endpoint,
            headers=headers,
            data=json.dumps(payload),
            timeout=120,
            stream=True,
        )
        response.raise_for_status()
        return _extract_stream_response(response)

    response = requests.post(
        endpoint, headers=headers, data=json.dumps(payload), timeout=120
    )
    response.raise_for_status()
    return _extract_non_stream_response(response.json())


def render_recommendations(
    seminars_by_id: dict[str, Seminar],
    recommended_ids: list[str],
    reasons: dict[str, str],
) -> None:
    st.subheader("Empfohlene Seminare")
    if not recommended_ids:
        st.info(
            "Noch keine Ergebnisse. Beschreibe kurz dein Ziel, dann zeige ich passende Seminare an."
        )
        return

    available_topics = sorted(
        {
            topic
            for seminar_id in recommended_ids
            if seminar_id in seminars_by_id
            for topic in seminar_topics(seminars_by_id[seminar_id])
        }
    )
    selected_topics: list[str] = []
    if available_topics:
        if hasattr(st, "pills"):
            selected_topics = (
                st.pills(
                    "Filter-Chips",
                    options=available_topics,
                    selection_mode="multi",
                    key="recommendation_topic_filters",
                )
                or []
            )
        else:
            selected_topics = st.multiselect(
                "Filter-Chips",
                options=available_topics,
                key="recommendation_topic_filters",
            )

    filtered_ids = recommended_ids
    if selected_topics:
        filtered_ids = [
            seminar_id
            for seminar_id in recommended_ids
            if seminar_id in seminars_by_id
            and any(
                topic in seminar_topics(seminars_by_id[seminar_id])
                for topic in selected_topics
            )
        ]
        if not filtered_ids:
            st.info("Für die gewählten Filter-Chips gibt es aktuell keine Treffer.")
            return

    for seminar_id in filtered_ids:
        seminar = seminars_by_id.get(seminar_id)
        if not seminar:
            continue

        with st.container(border=True):
            st.markdown(f"#### {seminar.title}")
            badges = [f"Kategorie: {seminar.category}"]
            seminar_dualis = seminar.dualis_code or "Keine Angabe"
            badges.append(f"Dualis: {seminar_dualis}")
            for topic in seminar_topics(seminar)[:3]:
                badges.append(f"Thema: {topic}")
            st.markdown(" ".join(f"`{badge}`" for badge in badges))
            reason = reasons.get(seminar.seminar_id, "")
            if reason:
                st.markdown(f"**Warum passend:** {reason}")
            st.markdown(f"**Fokus:** {seminar.focus or 'Keine Angabe'}")
            st.markdown(
                f"**Voraussetzungen:** {seminar.requirements or 'Keine Angabe'}"
            )

            with st.expander("Details anzeigen"):
                if seminar.content:
                    st.markdown("**Inhalte**")
                    st.markdown(seminar.content)
                if seminar.methods:
                    st.markdown("**Methoden**")
                    st.markdown(seminar.methods)
                if seminar.raw_markdown:
                    st.markdown("**Katalogauszug**")
                    st.markdown(seminar.raw_markdown)


def main() -> None:
    st.set_page_config(
        page_title="Seminarfinder-Chatbot",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.title("🎓 Seminarfinder-Chatbot")
    st.write("Seminarfinder für die Fükom-Seminare.")

    catalog_file = os.getenv("CATALOG_FILE", DEFAULT_CATALOG_FILE)
    llm_api_key = os.getenv("LLM_API_KEY", "")
    llm_endpoint = os.getenv("LLM_API_URL", DEFAULT_LLM_ENDPOINT)
    llm_model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
    llm_stream = os.getenv("LLM_STREAM", "false").lower() in {"1", "true", "yes"}
    try:
        llm_max_tokens = _read_positive_int_env("LLM_MAX_TOKENS", DEFAULT_MAX_TOKENS)
    except ValueError as exc:
        st.error(f"Ungültige LLM-Konfiguration: {exc}")
        st.stop()

    with st.sidebar:
        st.header("Konfiguration")
        st.caption("Der Katalog wird immer automatisch aus der Datei im Repo geladen.")
        st.text_input("Katalog-Datei", value=catalog_file, disabled=True)
        st.text_input("LLM API URL", value=llm_endpoint, disabled=True)
        st.text_input("LLM Modell", value=llm_model, disabled=True)
        st.text_input(
            "Streaming", value="Aktiv" if llm_stream else "Inaktiv", disabled=True
        )
        st.text_input(
            "Max. Antwort-Tokens",
            value=str(llm_max_tokens),
            disabled=True,
        )
        st.text_input(
            "LLM_API_KEY gesetzt",
            value="Ja" if llm_api_key else "Nein",
            disabled=True,
        )

    try:
        file_mtime = catalog_mtime(catalog_file)
        catalog_cache_key = (catalog_file, file_mtime)
        if st.session_state.get("catalog_cache_key") != catalog_cache_key:
            st.session_state["catalog_text"] = load_catalog_from_file(
                catalog_file, file_mtime
            )
            st.session_state["seminars"] = parse_seminars_from_catalog(
                st.session_state["catalog_text"]
            )
            st.session_state["catalog_cache_key"] = catalog_cache_key
    except (OSError, ValueError) as exc:
        st.error(
            "Katalog konnte nicht geladen werden. "
            "Bitte prüfe CATALOG_FILE und den Dateipfad.\n\n"
            f"Fehler: {exc}"
        )
        st.stop()

    if not st.session_state.get("seminars"):
        st.error(
            "Im Katalog wurden keine Seminare erkannt. Bitte prüfe die Struktur der Katalogdatei."
        )
        st.stop()

    if "last_recommendations" not in st.session_state:
        st.session_state["last_recommendations"] = []
    if "last_reasons" not in st.session_state:
        st.session_state["last_reasons"] = {}

    if not llm_api_key:
        st.error(
            "LLM_API_KEY ist nicht gesetzt. Bitte als Umgebungsvariable konfigurieren."
        )
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hi! Ich berate dich bei der Seminarwahl anhand des Katalogs. Was suchst du?",
            }
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    seminars_by_id = {
        seminar.seminar_id: seminar for seminar in st.session_state["seminars"]
    }
    user_prompt = st.chat_input("z. B. Ich möchte meine Selbstsicherheit steigern.")
    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with (
            st.chat_message("assistant"),
            st.spinner("Ich suche passende Seminare im Katalog …"),
        ):
            try:
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                    if m["role"] in {"user", "assistant"}
                ]
                raw_answer = llm_chat_openai_compatible(
                    api_key=llm_api_key,
                    model=llm_model,
                    endpoint=llm_endpoint,
                    system_prompt=build_system_prompt(
                        catalog_text=st.session_state["catalog_text"],
                        seminars=st.session_state["seminars"],
                        top_n=DEFAULT_RESULT_COUNT,
                    ),
                    history=history,
                    stream=llm_stream,
                    max_tokens=llm_max_tokens,
                )
                answer, recommended_ids, reasons = parse_recommendation_response(
                    raw_text=raw_answer,
                    seminars=st.session_state["seminars"],
                    user_prompt=user_prompt,
                    top_n=DEFAULT_RESULT_COUNT,
                )
                st.session_state["last_recommendations"] = recommended_ids
                st.session_state["last_reasons"] = reasons
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                answer = (
                    "Beim Aufruf der LLM API ist ein Fehler aufgetreten. "
                    "Bitte prüfe API-Key, URL und Modell.\n\n"
                    f"Fehler: {exc}"
                )
                st.session_state["last_recommendations"] = []
                st.session_state["last_reasons"] = {}

            st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})

    render_recommendations(
        seminars_by_id=seminars_by_id,
        recommended_ids=st.session_state["last_recommendations"],
        reasons=st.session_state["last_reasons"],
    )


if __name__ == "__main__":
    main()
