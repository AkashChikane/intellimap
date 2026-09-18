# IntelliMap — product information

Hackathon briefing for team **IntelliMap**. This is the full description of what the application is, who it is for, and how it finds issues.

For a slide-by-slide pitch, use [presentation.md](presentation.md). To run the demo, use [RUNBOOK.md](RUNBOOK.md) and [WINDOWS.md](WINDOWS.md).

---

## One sentence

IntelliMap turns a Volkswagen architecture Excel extract into a **scoped, traceable context diagram** for one decision, then **finds and highlights issues** on that diagram — first with deterministic checks, then with optional AI analysis.

It is decision support, not a system of record.

---

## Who it is for

Internal Volkswagen architecture and process work:

- Enterprise architects who receive a multi-sheet landscape extract and need a **context diagram**, not the whole estate.
- Process owners who need to see **which applications support a business process**, and whether that picture is trustworthy.
- Domain or information-object owners who need **what talks to what**, including unresolved and sensitive flows.
- Reviewers who must **spot data-quality and risk issues** before a diagram is copied into a decision pack.

No login. The demo runs locally. Org AI (VW LLMaaS / OpenAI-compatible) is optional and configured only in `.env`.

---

## The problem

Volkswagen architecture landscapes live in Excel. Typical extracts have many sheets: applications, directed relationships, interfaces, information objects, business processes, ownership, and already-known data-quality gaps.

Those workbooks are wide, messy, and incomplete:

- Names are not unique. IDs are the real keys.
- Rows point at application IDs that are missing from the catalog.
- Cycles, retired systems on critical paths, and Confidential / PII / PCI flows sit in the same file as ordinary hygiene issues.
- Dumping the **full** graph onto a slide is unusable. Architects need **one frame**: this application, this process, this domain, or this information object.

The question IntelliMap answers is: **what is in scope for this decision, and can I trust it?**

---

## The job of the application

IntelliMap has two jobs, and both must stay visible:

1. **Draw a scoped context diagram** from the workbook — only the neighbourhood of the chosen frame, with source rows still attached.
2. **Find and highlight issues** in that landscape:
   - **Visually** on the graph (unresolved nodes stay on the canvas; findings sit beside the diagram).
   - **Through AI analysis** (insights, semantic Find, review scan, sidebar assistant) — always labelled as interpretation, never as invented architecture.

It does **not** invent relationships. Unresolved foreign keys are **shown**, not dropped. Confidential / PII / PCI is a **sensitivity flag**, not a defect.

---

## What you get in a run

1. Upload a `.xlsx` landscape, or load the bundled sample (`data/IntelliMap_Architecture_Landscape.xlsx`, 60 applications).
2. **Workbook** — Excel-style sheet tabs, row preview, include or omit sheets for this run.
3. **Findings review** — every check explains what it means and how to fix it. Deterministic autofixes and an optional AI scan can be accepted or rejected. Download a corrected workbook.
4. **Context explorer** — interactive graph for one observation frame, inspector, findings sidebar, Find (`Ctrl+K` / `⌘K`), and a frame-grounded assistant.
5. **Export** — SVG (navy / paper / gray), JSON graph, markdown summary, and the reviewed Excel.

English and German UI. Light mode by default, with dark mode.

---

## How issues are found

### Layer 1 — source facts

Whatever was in the Excel sheets. IntelliMap stores a normalized SQLite model. It does not “clean away” broken references.

### Layer 2 — deterministic findings (visual)

Rules run on the stored model. Findings are grouped into four lanes:

| Lane | Meaning | Examples |
| --- | --- | --- |
| **Blocker** | The ID graph is broken or incomplete | Missing primary ID, duplicate ID, unresolved `ApplicationID`, missing FK |
| **Risk** | Architecture / process risk, not a deleted edge | Dependency cycles, high centrality, retired app on a critical path, retired app still supporting a critical process |
| **Quality** | Hygiene | Name vs catalog mismatch, missing ownership, inverted lifecycle dates, orphan interface, no process mapping |
| **Sensitive** | Classification flag | Information flows marked Confidential, PII, or PCI |

Unresolved applications appear as **unresolved nodes** on the diagram so the hole is visible. You can hide them for a cleaner picture without dropping the finding.

Each finding cites sheet and row, explains the rule, and (when possible) offers an autofix you must accept. Nothing is applied silently.

### Layer 3 — AI analysis (optional)

AI is off unless a key is configured (`LLM_PROVIDER=gemini` or `openai`, including VW LLMaaS). Ingest and deterministic graphs still work without it.

| Surface | What it does | Trust rule |
| --- | --- | --- |
| **AI scan** on review | Suggests extra semantic issues on the workbook | Accept or reject; not source fact |
| **AI insights** on the frame | Interprets the current scoped graph | Labelled “not architecture ground truth”; accept / reject |
| **AI Find** (`Ctrl+K`) | Semantic search (“billing bottleneck”, “retired EDI”) | Jumps only to IDs that already exist |
| **Sidebar assistant** | Answers from the current frame; can focus / highlight nodes, change hops or view | Actions only for IDs already in the graph. Drop a node into chat for extra context |
| **AI-enhanced / AI-abstract views** | Alternate layouts of the same scoped graph | Must use existing IDs only |

If the model is down, stay on the deterministic view and text Find. The diagram does not depend on the LLM.

---

## Observation frames

The explorer never draws the whole estate. You pick one seed:

| Frame | Question |
| --- | --- |
| Application | What sits around this system (1 or 2 hops)? |
| Business process | Which applications support this process? |
| Domain | What is in this domain neighbourhood? |
| Information object | Where does this information move? |

Hops are 1 or 2. Views: deterministic, AI-enhanced, AI-abstract.

---

## Expected workbook sheets

Header names are aliased (case, spaces, punctuation). Canonical sheets:

| Sheet | Role |
| --- | --- |
| Applications | Catalog. Hub key is `ApplicationID`. |
| Relationships | Directed dependencies between applications. |
| Interfaces | Technical connections (provider → consumer). |
| InformationObjects | What moves, including classification. |
| BusinessProcesses | Which applications support which processes. |
| ApplicationOwnership | Ownership, kept separate from the catalog on purpose. |
| KnownDataQualityGaps | Gaps already recorded in the source landscape. |

Replace the sample with a real Volkswagen extract when one is approved. Application code is not hard-coded to sample IDs.

---

## Principles (do not compromise in the pitch)

- No login in this slice.
- Application IDs are keys. Names are labels.
- Unresolved FKs stay visible.
- Directed relationships only; never invent edges.
- Sensitive classification is a flag, not a defect.
- Source facts, deterministic findings, and AI stay in separate layers.
- AI is optional, labelled, and only applied when the user accepts it.

---

## Stack (for judges who ask)

| Layer | Choice |
| --- | --- |
| UI | React (CRA), React Router, [@xyflow/react](https://reactflow.dev/) |
| API | Python FastAPI, SQLite (WAL), openpyxl, NetworkX |
| AI | Gemini (local test) or OpenAI-compatible / VW LLMaaS via `.env` |
| i18n | English / German |
| Packaging | Monorepo, `start.sh` / `start.bat`, no Docker |

Palette: `#6091C3`, `#1F2F57`, `#FDFAF9`, `#A8A8A8`.

---

## Suggested 8-minute demo

1. Header shows **API ready**. Load sample landscape (or a real extract).
2. Workbook tabs — treat it like Excel. Optionally omit `KnownDataQualityGaps`.
3. Findings board — walk the four lanes. Accept one autofix. Optional **Scan with AI**. Download fixed Excel.
4. Open context explorer (sample seed is often Order Management System, `APP-0005`).
5. Hide side panels so the diagram has room. **Find** → `OMS` or `APP-0005` → gold highlight at 150% zoom.
6. AI Find: “retired EDI” or “billing bottleneck”.
7. Show assistant: “Focus the seed application” or drop a node into chat.
8. Export SVG. Download Excel from the explorer toolbar.

---

## What this is not

- Not a CMDB replacement.
- Not an authoring tool that invents target architecture.
- Not CopilotKit in this slice (plain assistant only).
- Not a hosted Volkswagen product — a hackathon prototype that can sit on a real extract and org LLM later.

---

## Further reading

| File | Use |
| --- | --- |
| [presentation.md](presentation.md) | Pitch slides / spoken script |
| [README.md](README.md) | Product overview |
| [RUNBOOK.md](RUNBOOK.md) | Setup, env, demo script |
| [WINDOWS.md](WINDOWS.md) | Windows install |
