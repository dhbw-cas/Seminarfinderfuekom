# Seminarfinder-Chatbot

Diese App berät Studierende bei der Seminarwahl mit einem LLM und nutzt den Seminar-Katalog als Wissensbasis.

## Verhalten

- Der Katalog wird **immer automatisch** aus einer Datei im Repo geladen.
- Standardpfad: `data/catalog.md`
- Der Chat nutzt eine OpenAI-kompatible Chat-Completions-API. Standard ist Scaleway Generative APIs.
- Antworten stützen sich auf den Katalog und bleiben im Chat kurz.
- Passende Seminare werden als strukturierte Ergebnisse direkt unter dem Chat angezeigt.
- Ergebnisse enthalten Filter-Chips und kompakte Badges (Kategorie, Dualis, Thema).

## Umgebungsvariablen

- `LLM_API_KEY` (Pflicht, bei Scaleway: Secret Key)
- `LLM_API_URL` (optional, Default: `https://api.scaleway.ai/v1/chat/completions`)
- `LLM_MODEL` (optional, Default: `mistral/mistral-small-3.2-24b-instruct-2506:fp8`)
- `LLM_STREAM` (optional, `true`/`false`, Default: `false`)
- `LLM_MAX_TOKENS` (optional, Default: `1000`)
- `CATALOG_FILE` (optional, Default: `data/catalog.md`)

## Lokal starten

```bash
uv sync
export LLM_API_KEY="..."
uv run streamlit run app.py
```

## Sliplane Deployment

Sliplane erkennt dieses Repo als Python-Projekt und baut es mit Railpack. Der
benötigte Streamlit-Startbefehl ist deshalb explizit in `railpack.json`
konfiguriert. Das `Dockerfile` bleibt als portable Docker-Variante im Repo.

1. In Sliplane als Deploy Source `GitHub` wählen.
2. Repository `dhbw-cas/Seminarfinderfuekom` auswählen.
3. Service als HTTP-Service exposen.
4. Healthcheck Route auf `/_stcore/health` setzen.
5. Environment-Variablen konfigurieren.

Railpack-Startbefehl aus `railpack.json`:

```bash
python -m streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true
```

Pflicht:

```text
LLM_API_KEY=...
```

Optional:

```text
LLM_API_URL=https://api.scaleway.ai/v1/chat/completions
LLM_MODEL=mistral/mistral-small-3.2-24b-instruct-2506:fp8
LLM_STREAM=false
LLM_MAX_TOKENS=1000
CATALOG_FILE=data/catalog.md
```

Sliplane setzt `PORT` automatisch. Der Railpack-Startbefehl liest diese Variable
zur Laufzeit und startet Streamlit auf `0.0.0.0:$PORT`.

## Streamlit Cloud (streamlit.io)

In den App-Secrets setzen:

```toml
LLM_API_KEY = "..."
LLM_API_URL = "https://api.scaleway.ai/v1/chat/completions"
LLM_MODEL = "mistral/mistral-small-3.2-24b-instruct-2506:fp8"
LLM_STREAM = "false"
LLM_MAX_TOKENS = "1000"
CATALOG_FILE = "data/catalog.md"
```

## Scaleway API-Test

Der Scaleway Secret Key wird als Bearer Token gesendet:

```bash
curl --request POST \
  --url https://api.scaleway.ai/v1/chat/completions \
  --header "Authorization: Bearer $LLM_API_KEY" \
  --header "Content-Type: application/json" \
  --data '{
    "model": "mistral/mistral-small-3.2-24b-instruct-2506:fp8",
    "messages": [
      {"role": "user", "content": "Antworte kurz auf Deutsch: Funktioniert die API?"}
    ],
    "max_tokens": 100,
    "temperature": 0.2
  }'
```

Die App nutzt für Textgenerierung `POST /v1/chat/completions` mit `Authorization: Bearer <LLM_API_KEY>`.
