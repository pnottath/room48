# Room 48

A Kerala-tradition (Parashari) astrology service that generates a full janma kundali from date, time, and place of birth. Computes the sidereal Rasi chart (Lahiri ayanamsa, whole-sign houses), detects classical yogas, builds the full 120-year Vimshottari dasha tree, and renders an LLM-narrated reading grounded strictly in the computed chart facts.

Available as a **CLI tool**, a **FastAPI REST service**, and an **offline mode** that runs entirely on your laptop with no internet (after one-time setup).

**👉 New to this?** Pick the right guide:
- **Want to share Room 48 with friends online?** See [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) (Railway/Render/ngrok).
- **Want Room 48 running locally with no internet?** See [`OFFLINE_SETUP.md`](OFFLINE_SETUP.md) (rules-only mode or with Ollama).

The rest of this README is the technical reference.


## Quick start — REST API

```bash
pip install -r requirements.txt
uvicorn kerala_astro.api.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

### Endpoints

| Method | Path                       | Purpose |
| ------ | -------------------------- | ------- |
| GET    | `/`                        | Service info |
| GET    | `/health`                  | Health probe |
| POST   | `/api/v1/horoscope`        | Full janma kundali (chart + yogas + dashas + interpretation + text report) |
| POST   | `/api/v1/chart`            | Rasi chart only |
| POST   | `/api/v1/dashas`           | Vimshottari dasha tree only |
| POST   | `/api/v1/yogas`            | Detected yogas only |
| POST   | `/api/v1/report-text`      | Plain-text human-readable report |
| POST   | `/api/v1/narrative`        | **LLM-generated flowing astrologer's reading** |
| GET    | `/api/v1/timezone`         | Resolve IANA timezone from lat/lon |

### Example request

```bash
curl -X POST http://localhost:8000/api/v1/horoscope \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Sample Native",
       "year": 1990, "month": 6, "day": 15,
       "hour": 7, "minute": 45,
       "latitude": 8.5241, "longitude": 76.9366,
       "timezone_name": "Asia/Kolkata",
       "place_name": "Thiruvananthapuram",
       "num_upcoming_dashas": 3
     }'
```

### Response shape (abbreviated)

```json
{
  "chart": {
    "lagna_rasi": "Mithunam",
    "janma_nakshatra": "Shatabhisha",
    "ganam": "Rakshasa",
    "planets": [ { "name": "Sun", "rasi": "Mithunam", "house": 1, "...": "..." } ],
    "houses": { "1": { "lord": "Mercury", "occupants": ["Sun","Jupiter"] } }
  },
  "yogas": [ { "name": "Durudhara Yoga", "category": "Chandra", "result": "..." } ],
  "dashas": [ { "lord": "Saturn", "start": "2011-07-17", "end": "2030-07-17",
                "sub_periods": [] } ],
  "current_mahadasha": { "lord": "Saturn", "narrative": "..." },
  "upcoming_mahadashas": [ { "lord": "Mercury", "narrative": "..." } ],
  "full_text_report": "...",
  "disclaimer": "..."
}
```

### Python client example

See `example_client.py`. Short version:

```python
import urllib.request, json
req = urllib.request.Request(
    "http://localhost:8000/api/v1/horoscope",
    data=json.dumps({
        "name": "Sample", "year": 1990, "month": 6, "day": 15,
        "hour": 7, "minute": 45,
        "latitude": 8.5241, "longitude": 76.9366,
        "timezone_name": "Asia/Kolkata",
    }).encode(),
    headers={"Content-Type": "application/json"},
)
result = json.loads(urllib.request.urlopen(req).read())
print(result["chart"]["lagna_rasi"])
```


## Quick start — Docker

```bash
docker compose up --build
```

The service starts at http://localhost:8000.


## Quick start — CLI

```bash
# Interactive
python -m kerala_astro.run

# JSON input
python -m kerala_astro.run kerala_astro/sample_birth.json
```


## Quick start — Offline (no internet)

```bash
# Pure rules-only mode (no LLM at all) — always works offline
python -m kerala_astro.offline --input sample_birth.json --mode rules -o reading.txt

# With local LLM via Ollama (after `ollama pull llama3.1:8b`)
python -m kerala_astro.offline --input sample_birth.json --mode ollama -o reading.md

# Auto — uses Ollama if running, falls back to rules
python -m kerala_astro.offline --input sample_birth.json
```

See [`OFFLINE_SETUP.md`](OFFLINE_SETUP.md) for the full step-by-step.


## LLM Narrative Layer

The structured `/horoscope` endpoint returns precise but mechanical data. The narrative layer takes that same computed chart and asks an LLM to render it as a flowing astrologer's reading — while strictly forbidding the LLM from inventing positions, dates, or yogas.

### How it works

```
Chart + yogas + dashas
   ├─→ build_chart_digest()   # canonical factual block (Markdown tables)
   ├─→ system_blocks(language, digest)   # 2 blocks, last marked CACHEABLE
   ├─→ async parallel:
   │      for each section: short brief → LLM.generate_async()
   └─→ assemble into full Markdown reading
```

The digest is the *only* source of facts the LLM is allowed to use. The system prompt explicitly forbids inventing yogas not in the digest, inventing dates, predicting death/illness, or giving medical/legal/financial instructions.

### Cost optimizations (built-in, on by default)

Room 48 stacks three independent cost levers:

| Lever | What it does | Savings |
| --- | --- | --- |
| **Anthropic prompt caching** | The system prompt + chart digest (~3KB stable text) is marked `cache_control: ephemeral`. The first section call writes it to Anthropic's cache; the next 6 sections read from cache at ~10% of normal input cost. | ~70-80% on input tokens within a single reading |
| **Response cache (disk)** | After generating a reading, the result is hashed (SHA256 of digest + options) and stored to `~/.room48/narrative_cache/`. Identical follow-up requests are served from disk with no LLM call. 30-day TTL. | 100% on repeat readings |
| **Parallel async generation** | All 7 sections fire concurrently via `asyncio.gather` and a single `AsyncAnthropic` client. | Same cost, ~7× faster wall time |

The narrative response includes a `usage` field with token counts and cache-hit telemetry so you can verify the savings empirically:
```json
"usage": {
  "response_cache_hit": false,
  "total_input_tokens":   850,
  "total_output_tokens": 4200,
  "cache_read_tokens": 18900,    // ← cached portion at 10% cost
  "cache_write_tokens": 3100,    // ← first-write at 1.25x cost
  "prompt_cache_hits": 6,
  "sections_generated": 7
}
```

To disable either cache for testing: pass `"use_response_cache": false` in the request, or run with the `--no-cache` flag in the CLI.

### Configuration

Set `ANTHROPIC_API_KEY` in your environment. Without it, the system falls back to an `EchoProvider` (no network calls, useful for pipeline tests).

The response cache lives at `$ROOM48_CACHE_DIR` (defaults to `~/.room48/narrative_cache`). On Docker, this is persisted as a named volume.

Adding other providers (OpenAI, local Llama, etc.) only requires implementing the `LLMProvider` interface in `narrative/llm_provider.py`.

### Use from CLI

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m kerala_astro.narrative.run kerala_astro/sample_birth.json
python -m kerala_astro.narrative.run kerala_astro/sample_birth.json --language manglish
python -m kerala_astro.narrative.run kerala_astro/sample_birth.json --section yogas --section current_dasha
python -m kerala_astro.narrative.run kerala_astro/sample_birth.json --no-cache    # skip response cache
```

To see a demo of what the output looks like *without* an API key (uses hand-crafted sample prose):

```bash
python -m kerala_astro.narrative.demo
```

### Use from the API

```bash
curl -X POST http://localhost:8000/api/v1/narrative \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Sample Native",
       "year": 1990, "month": 6, "day": 15,
       "hour": 7, "minute": 45,
       "latitude": 8.5241, "longitude": 76.9366,
       "timezone_name": "Asia/Kolkata",
       "language": "english",
       "sections": ["overview","personality","yogas","current_dasha"]
     }'
```

Response shape:
```json
{
  "language": "english",
  "model": "claude-opus-4-7",
  "provider": "anthropic",
  "sections": [
    { "section": "overview", "title": "Opening", "text": "Namaskaram, Sample Native..." },
    { "section": "yogas", "title": "Yoga Phalam — ...", "text": "..." }
  ],
  "markdown": "# Janma Kundali — Astrological Reading\n\n## Opening\n\n...",
  "disclaimer": "..."
}
```

### Available sections

`overview`, `personality`, `bhava`, `yogas`, `current_dasha`, `upcoming`, `closing`

### Languages

- `english` — clear English
- `manglish` — natural Malayalam-English mix in Latin script
- `malayalam` — formal Malayalam in Latin transliteration

### Sample output

See `sample_narrative_output.md` for the full reading produced by the demo for the Thiruvananthapuram 1990 sample birth.




```
kerala_astro/
├── core/                       # Pure computation, no I/O
│   ├── constants.py            # Rasis, nakshatras, dasha years, dignities
│   ├── chart.py                # Swiss Ephemeris sidereal calculation
│   ├── dasha.py                # Vimshottari MD/AD/PAD calculator
│   ├── yogas.py                # 14+ yoga detectors
│   └── interpret.py            # Dasha-phalam paragraph generator
├── agent/
│   └── horoscope_agent.py      # Orchestrates all modules; produces text report
├── narrative/                  # LLM narrative layer
│   ├── llm_provider.py         # Provider interface + Anthropic sync+async impl
│   ├── digest.py               # Build factual ground-truth digest
│   ├── prompts.py              # Astrologer persona + per-section briefs
│   ├── cache.py                # SHA256-keyed disk cache for responses
│   ├── engine.py               # NarrativeEngine — async, cached, parallel
│   ├── run.py                  # CLI for narrative generation
│   └── demo.py                 # Mocked demo (works without API key)
├── api/                        # FastAPI service
│   ├── main.py                 # Routes, error handling, CORS
│   ├── schemas.py              # Pydantic request/response models
│   └── converters.py           # Internal dataclasses → API models
├── run.py                      # CLI entry point
├── example_client.py           # API client example
├── DEPLOYMENT_GUIDE.md         # Beginner-friendly deployment walkthrough
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

**Clean separation**: `core/` knows nothing about HTTP. `api/` imports from
`core/` but never the other way. You can swap FastAPI for Flask, gRPC, or
anything else without touching the astrology engine.


## Yogas detected

Pancha Mahapurusha (Ruchaka, Bhadra, Hamsa, Malavya, Sasa), Gajakesari,
Budhaditya, Chandra-Mangala, Sunapha / Anapha / Durudhara / Kemadruma,
Raja yogas (Kendra-Trikona lord pairs + Parivartana), Dhana yogas
(2/5/9/11 lord combinations), Neechabhanga Raja Yoga, Vipareeta Raja Yoga,
Kuja Dosha, Kalasarpa, Sarpa Dosha (5th house), Saraswati Yoga.


## Verification

Reference values for `sample_birth.json` (15 June 1990, 07:45 IST, Thiruvananthapuram):

| Quantity        | Computed                              |
| --------------- | ------------------------------------- |
| Ayanamsa Lahiri | 23.7237°                              |
| Lagna           | Mithunam 22.27° (Punarvasu pada 1)    |
| Sun             | Mithunam 0.01°                        |
| Moon            | Kumbham 16.23° (Shatabhisha pada 3)   |
| Saturn          | Makaram 0.33° R (Own sign)            |
| Ganam / Nadi    | Rakshasa / Aadi                       |


## Production notes

- **CORS** is open (`*`) by default for development. In production, replace
  `allow_origins=["*"]` in `api/main.py` with trusted origins.
- **Rate limiting** is not built in — add via reverse-proxy (nginx/Cloudflare)
  or middleware like `slowapi` if exposing publicly.
- **Authentication** can be layered with FastAPI dependencies.
- The Swiss Ephemeris data files bundled with `pyswisseph` cover roughly
  1800–2200 CE; for births outside this range, additional ephemeris files
  must be supplied via `swe.set_ephe_path`.


## Guardrails

The agent will not predict death, terminal illness, or specific accidents.
All language is probabilistic (tendencies, themes) per Kerala tradition's
emphasis on karma and parihara. Every response includes a `disclaimer` field.


## Classical sources

- Brihat Parashara Hora Shastra
- Phaladeepika by Mantreswara
- Krishneeyam (Kerala Prasna text)
- Prasna Marga
- Jataka Parijata


## Roadmap

- Divisional charts: Navamsa (D9) for marriage, Dasamsa (D10) for career
- Ashtakavarga (Sarvashtakavarga + bhinnashtakavarga)
- Gochara (transits) including Sade Sati detection
- Porutham (Kerala 10-aspect marriage compatibility)
- Muhurta (electional astrology) calculator
- Parihara recommendations: temples, mantras, daana, vrata
- South Indian square chart SVG/PNG renderer
- LLM narrative layer using API responses as ground truth
- Multi-language output (Malayalam, Sanskrit toggle)
- Async batch endpoint for processing many charts
