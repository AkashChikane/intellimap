# IntelliMap runbook

Operator guide: first-time setup, demo, environment, and recovery. Product overview lives in [README.md](README.md).

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.11+ | `python3` on Mac/Linux, `py -3` or `python` on Windows |
| Node.js | 18+ | Node 20 is fine. Used only for the CRA frontend |
| npm | ships with Node | `npm install` runs inside `frontend/` |
| Gemini key **or** OpenAI-compatible key | — | AI features (insights, chat, semantic Find, review scan) need a key. Ingest and deterministic graphs work without one |

No Docker. No database server. SQLite is created under `backend/storage/` at first run (gitignored).

## Ports

| Service | URL |
| --- | --- |
| UI | http://localhost:3000 |
| API | http://127.0.0.1:8000 |
| OpenAPI | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/api/health |

The CRA dev server proxies `/api` to `http://127.0.0.1:8000`. Start the API first.

## First-time setup (Mac / Linux)

```bash
git clone https://github.com/AkashChikane/intellimap.git
cd intellimap
cp .env.example .env
```

Edit `.env` and set at least:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash-lite
```

Two terminals:

```bash
chmod +x start.sh start-frontend.sh
./start.sh
```

```bash
./start-frontend.sh
```

`start.sh` creates `backend/.venv`, installs Python deps, generates the sample workbook if missing, and runs uvicorn with `--reload`. `start-frontend.sh` runs `npm install` if needed and starts CRA on port 3000.

Open http://localhost:3000. Health should show `llm_ready: true` when the key is valid: http://127.0.0.1:8000/api/health

## First-time setup (Windows)

```bat
git clone https://github.com/AkashChikane/intellimap.git
cd intellimap
copy .env.example .env
```

Fill `.env` as above.

Command Prompt 1:

```bat
start.bat
```

Command Prompt 2:

```bat
start-frontend.bat
```

Open http://localhost:3000

## Environment

Never commit `.env`. Copy from `.env.example`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `gemini` | `gemini` or `openai` |
| `GEMINI_API_KEY` | empty | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | Cheaper Flash-Lite; change if the model is retired |
| `OPENAI_API_KEY` | empty | Org or OpenAI key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Org OpenAI-compatible base URL |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model id on that endpoint |
| `HOST` | `127.0.0.1` | API bind host |
| `PORT` | `8000` | API port |

**Local testing:** Gemini.

**Org demo:** switch provider, do not keep a Gemini key in the demo machine if policy forbids it.

```
LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://your-org-endpoint/v1
OPENAI_MODEL=gpt-4o-mini
```

Restart the API after changing `.env` (uvicorn `--reload` picks up code, not always env).

## Demo script (about 8 minutes)

1. http://localhost:3000 — confirm **API ready** in the header.
2. **Load sample landscape** (or drop `data/IntelliMap_Architecture_Landscape.xlsx`).
3. **Workbook** — tabs behave like Excel. Open Applications, skim rows. Open KnownDataQualityGaps and uncheck **Include in this run** if you want to show omit.
4. **Review findings** — explain the four lanes: blockers break IDs, risks need a decision, quality is hygiene, sensitive is a classification flag.
5. Filter **Autofixable**. Accept one fix (for example a placeholder for an unresolved `ApplicationID`, or a name mismatch). Optionally **Scan with AI**, accept or reject. **Download fixed Excel**.
6. **Open context explorer**. Suggested frame is usually Order Management System (`APP-0005`).
7. Hide findings/inspector so the diagram has room. **Find** (`⌘K` / `Ctrl+K`) → Text → `APP-0005` or `OMS`. Enter jumps and zooms to 150%. Esc clears the highlight.
8. Switch Find to **AI**, search “billing bottleneck” or “retired EDI”.
9. **Show assistant**. Try **Focus the seed application** or drop a node into the composer.
10. Export SVG (navy/paper/gray). **Download Excel** from the explorer toolbar as well.

If Gemini is 503 / high demand, stay on deterministic view and text Find. Ingest and graphs do not require the LLM.

## Regenerating the sample workbook

```bash
# Mac/Linux, venv active or:
backend/.venv/bin/python backend/generate_sample.py
```

Writes `data/IntelliMap_Architecture_Landscape.xlsx`. IDs in that file are **sample data**, never referenced by application code.

To use a real extract, drop the `.xlsx` on the upload step. Keep the seven expected sheets (names are aliased).

## Manual start (if scripts fail)

API:

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate   # Windows: backend\.venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

UI:

```bash
cd frontend
npm install
BROWSER=none PORT=3000 npm start
```

## Stopping

Ctrl+C both terminals. SQLite files in `backend/storage/` can be deleted to wipe ingest runs.

If a port is stuck:

```bash
lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill -9
lsof -tiTCP:3000 -sTCP:LISTEN | xargs kill -9
```

Windows: Task Manager, or `netstat -ano | findstr :8000` then `taskkill /PID <pid> /F`.

## Health checks

```bash
curl -sS http://127.0.0.1:8000/api/health
```

Expect `"ok": true`. `"llm_ready": true` means a key is present. `"sample_present": true` means the sample xlsx exists.

If the UI shows **API offline**, the proxy cannot reach :8000. Start `./start.sh` first.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `npm` ENOENT / install at repo root | Always `cd frontend` (or use `start-frontend.sh`) |
| Gemini 404 on model | Set `GEMINI_MODEL` to a live model (default `gemini-2.5-flash-lite`) |
| Gemini 503 high demand | Retry later; deterministic path still works |
| `database disk image is malformed` | Stop API, delete `backend/storage/intellimap.db*` and ingest again |
| Export SVG used to leave the page | Use the **Export SVG** button (blob download). Do not rely on a raw `/api/.../export/svg` navigation |
| Find returns nothing for a nickname | Use Text with the `ApplicationID`, or switch to AI semantic search |
| Chat / AI scan 503 | Key missing, wrong provider, or upstream quota. Check `.env` and `/api/health` |
| Windows `python` not found | Install Python 3.11+ and tick “Add to PATH”, or use `py -3` |
| Sample xlsx missing | `python backend/generate_sample.py` |

## What not to do

- Do not commit `.env` or API keys.
- Do not invent workbook IDs or relationships in demos — if it is not in the sheet, say so.
- Do not treat AI cards as architecture ground truth.
- CopilotKit is out of this slice (plain assistant only).

## Switching machines for the org demo

1. Copy the repo (no `.env`).
2. Set `LLM_PROVIDER=openai` and the org base URL + key.
3. Confirm `/api/health` shows `llm_provider: openai` and `llm_ready: true`.
4. Run the demo script. Prefer **Load sample landscape** unless a real extract is approved.
