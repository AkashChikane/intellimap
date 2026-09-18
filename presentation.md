# IntelliMap — presentation

Spoken pitch and slide outline for the hackathon. Full product detail lives in [information.md](information.md). Demo steps live in [RUNBOOK.md](RUNBOOK.md).

**Length:** about 8 minutes plus live demo.  
**Audience:** Volkswagen internal architecture / process / hackathon jury.  
**Claim to land:** we do not draw the whole estate. We draw **one decision**, then **show what is wrong with it** — on the diagram and with AI.

---

## Slide 1 — Title

**IntelliMap**  
Scoped context diagrams for Volkswagen architecture decisions  
*Find the issues. Don’t bury them in the estate.*

Team IntelliMap · hackathon prototype · no login · Excel in, diagram out

*Speaker: name the team. One breath. Then the problem.*

---

## Slide 2 — The situation inside Volkswagen

Architecture and process landscapes arrive as **multi-sheet Excel**.

Applications, directed relationships, interfaces, information objects, business processes, ownership, known gaps.

That file is the input everyone already has. It is also incomplete.

*Speaker: judges know this pain. Don’t lecture Excel. Point at the extract.*

---

## Slide 3 — Why a full-estate picture fails

- Names are not unique. **IDs** are.
- Rows point at applications that are **not in the catalog**.
- Retired systems still sit on **critical processes**.
- Confidential / PII / PCI flows sit next to ordinary hygiene issues.
- A slide with every box is not a decision tool.

**The real question:** *What is in scope for this decision, and can I trust it?*

---

## Slide 4 — What IntelliMap is

A local app that:

1. Ingests the Volkswagen landscape workbook.
2. Validates it and explains every finding.
3. Draws a **scoped, traceable context diagram** for **one** application, business process, domain, or information object.
4. **Highlights issues visually** on that diagram.
5. Offers **AI analysis** on the same frame — labelled, optional, never invented architecture.

Decision support. Not a CMDB. Not a system of record.

---

## Slide 5 — The job, in one line

**Draw the neighbourhood. Surface the holes.**

Visual: unresolved nodes stay on the canvas. Findings sit beside the graph. Cycles and sensitive flows are marked, not deleted.

AI: insights, semantic search, review scan, sidebar assistant — only on IDs that already exist.

---

## Slide 6 — Two ways issues show up

| Visual (always) | AI (optional) |
| --- | --- |
| Unresolved `ApplicationID` as a node you can see | Insights on the current frame |
| Four lanes: blocker, risk, quality, sensitive | Semantic Find (`Ctrl+K`) |
| Sheet + row cited on every finding | AI scan on the workbook |
| Autofix only after you accept | Assistant can focus / highlight nodes |

If the LLM is down, the diagram still works.

*Speaker: this is the product differentiator. Pause here.*

---

## Slide 7 — Trust model (say this out loud)

Three layers, never mixed:

1. **Source facts** — the Excel.
2. **Deterministic findings** — rules (missing IDs, cycles, lifecycle, ownership, sensitive classification).
3. **AI interpretation** — suggestion only. Accept or reject.

We **never invent a relationship**.  
Unresolved foreign keys are **shown**, not dropped.  
Confidential / PII / PCI is a **flag**, not a defect.

---

## Slide 8 — Live demo path

1. Load sample landscape (or approved extract).
2. Workbook tabs — it should feel like Excel. Omit a sheet if you want.
3. Findings board — accept one autofix. Optional AI scan. Download fixed Excel.
4. Open explorer — one application (sample: Order Management System).
5. Find `OMS` → jump, 150% zoom, gold highlight.
6. AI Find: “retired EDI” / “billing bottleneck”.
7. Assistant: focus the seed, or drop a node into chat.
8. Export SVG + Excel.

*Speaker: hide findings/inspector so the diagram has room. Keep EN or flip to DE if the room is German.*

---

## Slide 9 — What a finding looks like

Each check answers:

- What is wrong (or flagged).
- Why it matters.
- How to fix it.
- Whether IntelliMap can apply a **placeholder** (you still accept).

Examples you can click in the demo:

- Unresolved application ID → node on the graph.
- Name does not match the catalog → IDs win, labels follow.
- Dependency cycle → risk, edge stays.
- Retired app on a critical process → risk.
- PII / PCI flow → sensitive, not an error.

---

## Slide 10 — Observation frames

Not the estate. One seed:

- **Application** — 1 or 2 hop neighbourhood
- **Business process** — supporting applications
- **Domain** — domain neighbourhood
- **Information object** — where the data moves

Same issues engine. Different question.

---

## Slide 11 — Why this fits Volkswagen process work

- Input is the extract they already produce.
- Output is a **context diagram** you can put in a decision pack (SVG).
- German / English toggle.
- Org model later: OpenAI-compatible **VW LLMaaS** via `.env` only — no keys in code.
- Deterministic path works on a locked-down laptop if AI is unavailable.

---

## Slide 12 — Stack (one slide, then move on)

React + xyflow · Python FastAPI · SQLite · NetworkX · Gemini or VW LLMaaS  
No Docker. `start.bat` / `start.sh`. Palette navy / steel / paper.

*Speaker: don’t live in the stack unless asked.*

---

## Slide 13 — What we did not build (on purpose)

- No login in this slice.
- No CopilotKit (plain assistant).
- No invented target architecture.
- No silent writes back to Excel — you download a reviewed file.

Honesty is part of the pitch.

---

## Slide 14 — Close

**IntelliMap** makes Volkswagen context diagrams **small enough to use** and **honest enough to trust**.

Issues are visible on the graph.  
AI is a lens, not the source of truth.

*Ask:* upload a real extract next; point the assistant at VW LLMaaS.

---

## Backup answers

**Does AI create edges?** No. Actions and views may only use IDs already in the scoped graph.

**What if the workbook is wrong?** That is the point. We highlight it. Unresolved stays on the canvas.

**Can we use a real landscape?** Yes. Same seven sheets (names are aliased). Sample IDs are data, not hard-coded in the app.

**EN/DE?** Toggle in the header. Default English.

**Windows demo?** [WINDOWS.md](WINDOWS.md) — `start.bat` then `start-frontend.bat`. Python 3.11–3.14 on PATH.

---

## Timing cheat sheet

| Minute | Beat |
| --- | --- |
| 0–1 | Title + Volkswagen Excel problem |
| 1–2 | Scoped diagram + find issues (visual + AI) |
| 2–3 | Trust layers |
| 3–7 | Live demo |
| 7–8 | Close + ask |
