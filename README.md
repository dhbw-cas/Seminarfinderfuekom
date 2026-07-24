# Seminarfinder-Chatbot

Diese App berät Studierende bei der Seminarwahl mit einem LLM und nutzt den Seminar-Katalog als Wissensbasis.

## Verhalten

- Der Katalog wird **immer automatisch** aus einer Datei im Repo geladen.
- Standardpfad: `data/catalog.md`
- Der Chat nutzt die OpenAI-kompatible Chat-Completions-API des IONOS AI Model Hub.
- Antworten stützen sich auf den Katalog und bleiben im Chat kurz.
- Passende Seminare werden als strukturierte Ergebnisse direkt unter dem Chat angezeigt.
- Ergebnisse enthalten Filter-Chips und kompakte Badges (Kategorie, Dualis, Thema).

## Umgebungsvariablen

- `IONOS_API_TOKEN` (Pflicht)
- `IONOS_API_URL` (optional, Default: `https://openai.inference.de-txl.ionos.com/v1/chat/completions`)
- `IONOS_MODEL` (optional, Default: `mistralai/Mistral-Small-24B-Instruct`)
- `IONOS_STREAM` (optional, `true`/`false`, Default: `false`)
- `IONOS_MAX_COMPLETION_TOKENS` (optional, Default: `1000`)
- `CATALOG_FILE` (optional, Default: `data/catalog.md`)

## Lokal starten

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export IONOS_API_TOKEN="..."
streamlit run app.py
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
IONOS_API_TOKEN=...
```

Optional:

```text
IONOS_API_URL=https://openai.inference.de-txl.ionos.com/v1/chat/completions
IONOS_MODEL=mistralai/Mistral-Small-24B-Instruct
IONOS_STREAM=false
IONOS_MAX_COMPLETION_TOKENS=1000
CATALOG_FILE=data/catalog.md
```

Sliplane setzt `PORT` automatisch. Der Railpack-Startbefehl liest diese Variable
zur Laufzeit und startet Streamlit auf `0.0.0.0:$PORT`.

## Streamlit Cloud (streamlit.io)

In den App-Secrets setzen:

```toml
IONOS_API_TOKEN = "..."
IONOS_API_URL = "https://openai.inference.de-txl.ionos.com/v1/chat/completions"
IONOS_MODEL = "mistralai/Mistral-Small-24B-Instruct"
IONOS_STREAM = "false"
IONOS_MAX_COMPLETION_TOKENS = "1000"
CATALOG_FILE = "data/catalog.md"
```

## IONOS API-Test

Token und Account-Zugriff lassen sich mit der Modellliste prüfen:

```bash
curl -H "Authorization: Bearer $IONOS_API_TOKEN" \
  https://openai.inference.de-txl.ionos.com/v1/models
```

Die App nutzt für Textgenerierung `POST /v1/chat/completions` mit `Authorization: Bearer <IONOS_API_TOKEN>`.
