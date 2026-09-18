# IntelliMap

Scoped, traceable enterprise-architecture **context diagrams** from a multi-sheet Excel landscape.

IntelliMap is a hackathon app for team **IntelliMap**. Upload an architecture workbook, validate it, optionally omit sheets and accept fixes, then inspect a regeneratable graph for **one** application, business process, domain, or information object — not the full estate.

The product is **decision support**. Source facts, deterministic findings, and AI interpretations stay in separate layers. Unresolved foreign keys stay on the canvas. Relationships are never invented.

**Run it:** see [RUNBOOK.md](RUNBOOK.md).

## Why this exists

Enterprise architecture extracts are wide, messy, and incomplete. Names are not unique. IDs collide with labels. Some applications are referenced but missing from the catalog. Dumping the whole graph on a slide is unusable.

IntelliMap answers: *what is in scope for this decision, and can I trust it?*

## What it does

1. **Ingest** a `.xlsx` landscape (or load the bundled sample).
2. **Workbook review** — Excel-style sheet tabs, row preview, include or omit sheets.
3. **Findings review** — each check explains what it means and how to fix it. Deterministic autofixes and an optional AI scan can be accepted or rejected. Download a corrected workbook.
4. **Context explorer** — scoped xyflow graph, inspector, SVG/JSON/summary export, and a frame-grounded assistant.
5. **Find** with `Ctrl+K` / `⌘K` (text or AI semantic search). Jump to a node at 150% zoom with a highlight that clears when Find is closed.

## Principles

- No login.
- Application IDs are the hub. Names are labels, not keys.
- Unresolved FKs are findings, not deletions.
- Directed relationships only; never invent edges.
- Confidential / PII / PCI flows are flagged as sensitive, not treated as defects.
- AI is optional, labeled, and only applied when you accept it.
- Nothing in application code is hard-coded to sample IDs.

## Expected workbook sheets

Header names are aliased (case, spaces, punctuation). Canonical sheets:

| Sheet | Role |
| --- | --- |
| Applications | Catalog. Every other sheet hangs off `ApplicationID`. |
| Relationships | Directed dependencies between applications. |
| Interfaces | Technical connections (provider → consumer). |
| InformationObjects | What moves, including classification. |
| BusinessProcesses | Which applications support which processes. |
| ApplicationOwnership | Ownership, kept separate from the catalog on purpose. |
| KnownDataQualityGaps | Gaps already recorded in the source landscape. |

Sample file: [`data/IntelliMap_Architecture_Landscape.xlsx`](data/IntelliMap_Architecture_Landscape.xlsx) (60 applications). Replace it with a real extract when you have one. Regenerate with `python backend/generate_sample.py`.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React (Create React App), React Router, [@xyflow/react](https://reactflow.dev/) |
| Backend | Python FastAPI, SQLite (WAL), openpyxl, NetworkX |
| AI | Gemini (local) or any OpenAI-compatible endpoint via `.env` |
| Packaging | Monorepo, `start.sh` / `start.bat`, no Docker |

Palette: `#6091C3`, `#1F2F57`, `#FDFAF9`, `#A8A8A8`.

```
backend/     FastAPI app, ingest, validation, graph, review, AI, SVG
frontend/     CRA UI (upload → workbook → review → explorer)
data/         Sample landscape workbook
start.sh      API (Mac/Linux)
start-frontend.sh
start.bat     API (Windows)
```

## Quick start

```bash
cp .env.example .env   # add GEMINI_API_KEY (or switch LLM_PROVIDER=openai)
./start.sh             # terminal 1 — API on :8000
./start-frontend.sh    # terminal 2 — UI on :3000
```

Open http://localhost:3000 — **Load sample landscape**.

VW LLMaaS smoke test (lists models, sends `Hi`):

```bash
backend/.venv/bin/python backend/test_llm.py
```

**Windows:** follow **[WINDOWS.md](WINDOWS.md)** (`start.bat` then `start-frontend.bat`). Operator notes and demo script: **[RUNBOOK.md](RUNBOOK.md)**.

API docs while running: http://127.0.0.1:8000/docs

## Explorer

- Four observation frames: application, business process, domain, information object.
- Views: deterministic, AI-enhanced, AI abstract.
- Hide unresolved nodes without dropping the underlying finding.
- Sidebar assistant is grounded in the current frame. It can focus a node, highlight apps, and propose diagram changes (hops, view, hide unresolved). Drop a node onto the composer for extra context.
- Export SVG (navy / paper / gray), JSON, markdown summary, and the **reviewed Excel**.

## License

Built for a hackathon. Add a license file if you need one for distribution.
