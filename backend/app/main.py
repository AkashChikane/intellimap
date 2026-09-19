from __future__ import annotations

import shutil
import traceback
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel

from .ai import chat as chat_mod
from .ai import insights as insights_mod
from .ai import search as search_mod
from .ai import views as views_mod
from .ai.provider import AIProviderError, available as ai_available, provider_name
from .config import BACKEND, DB_PATH, SAMPLE_XLSX, STORAGE
from .db.store import Store
from .graph.builder import build_context, list_frames
from .graph.svg import available_themes, render_svg
from .ingest.export_xlsx import workbook_bytes
from .ingest.headers import EXPECTED_SHEETS
from .ingest.pipeline import ingest_file, rebuild_normalized, summarize
from .review.fixes import accept_all_autofixes, apply_fix, enrich_findings
from .review.scan import scan_review

app = FastAPI(title="IntelliMap", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = Store(DB_PATH)


class InsightReview(BaseModel):
    status: str


class ChatBody(BaseModel):
    frame_type: str
    frame_id: str
    hops: int = 1
    messages: list[dict]
    dropped: list[dict] = []
    hide_unresolved: bool = False


class SearchBody(BaseModel):
    query: str
    frame_type: str
    frame_id: str
    hops: int = 1
    hide_unresolved: bool = False
    mode: str = "ai"


class FrameBody(BaseModel):
    frame_type: str
    frame_id: str
    hops: int = 1
    hide_unresolved: bool = False


class OmitSheetsBody(BaseModel):
    omit: list[str] = []


class FixReviewBody(BaseModel):
    status: str


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "name": "IntelliMap",
        "llm_provider": provider_name(),
        "llm_ready": ai_available(),
        "sample_present": SAMPLE_XLSX.exists(),
    }


@app.post("/api/ingest")
async def ingest(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Upload an .xlsx workbook")
    STORAGE.mkdir(parents=True, exist_ok=True)
    dest = STORAGE / file.filename
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    try:
        return ingest_file(store, dest)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(400, f"Ingest failed: {exc}") from exc


@app.post("/api/ingest/sample")
def ingest_sample():
    path = SAMPLE_XLSX
    if not path.exists():
        import sys

        sys.path.insert(0, str(BACKEND))
        from generate_sample import write_workbook

        write_workbook(path)
    return ingest_file(store, path)


@app.get("/api/runs/latest")
def latest_run():
    run = store.latest_run()
    if not run:
        raise HTTPException(404, "No ingest runs yet")
    return summarize(store, run["id"])


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Unknown run")
    return summarize(store, run_id)


@app.get("/api/runs/{run_id}/findings")
def get_findings(
    run_id: str,
    severity: str | None = None,
    rule_id: str | None = None,
    q: str | None = None,
):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    items = enrich_findings(store, run_id)
    if severity:
        items = [f for f in items if f["severity"] == severity]
    if rule_id:
        items = [f for f in items if f["rule_id"] == rule_id]
    if q:
        needle = q.lower()
        items = [
            f
            for f in items
            if needle in (f.get("title") or "").lower()
            or needle in (f.get("entity_id") or "").lower()
            or needle in (f.get("description") or "").lower()
        ]
    return {"items": items, "total": len(items)}


@app.get("/api/runs/{run_id}/sheets/{sheet}/preview")
def sheet_preview(run_id: str, sheet: str, limit: int = 40):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    if sheet not in EXPECTED_SHEETS:
        raise HTTPException(404, "Unknown sheet")
    rows = store.raw_rows(run_id, sheet, limit=max(1, min(limit, 200)))
    headers = []
    for row in rows:
        for header in row.get("original") or {}:
            if header and header not in headers:
                headers.append(header)
    report = next((s for s in store.sheet_reports(run_id) if s["sheet"] == sheet), None)
    omitted = sheet in store.omitted_sheets(run_id)
    return {
        "sheet": sheet,
        "omitted": omitted,
        "headers": headers,
        "rows": [
            {
                "source_row": r.get("row_number"),
                "values": r.get("original") or {},
            }
            for r in rows
        ],
        "row_count": (report or {}).get("row_count") or len(rows),
        "truncated": bool(report and (report.get("row_count") or 0) > len(rows)),
    }


@app.get("/api/runs/{run_id}/review")
def get_review(run_id: str):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    summary = summarize(store, run_id)
    items = enrich_findings(store, run_id)
    open_items = [f for f in items if f.get("status") == "open"]
    autofixable = [
        f
        for f in open_items
        if any(fx.get("status") == "proposed" and fx.get("autofixable") for fx in f.get("fixes") or [])
    ]
    return {
        **summary,
        "findings": items,
        "open_total": len(open_items),
        "autofixable_total": len(autofixable),
        "ai_ready": ai_available(),
    }


@app.post("/api/runs/{run_id}/review/sheets")
def omit_sheets(run_id: str, body: OmitSheetsBody):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    unknown = [s for s in body.omit if s not in EXPECTED_SHEETS]
    if unknown:
        raise HTTPException(400, f"Unknown sheets: {', '.join(unknown)}")
    return rebuild_normalized(store, run_id, body.omit)


@app.post("/api/runs/{run_id}/review/ai-scan")
def review_ai_scan(run_id: str):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    try:
        created = scan_review(store, run_id)
    except AIProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    summary = summarize(store, run_id)
    return {
        **summary,
        "created": created,
        "findings": enrich_findings(store, run_id),
        "disclaimer": "AI suggestions are not architecture ground truth.",
    }


@app.post("/api/runs/{run_id}/review/fixes/accept-all")
def review_accept_all(run_id: str):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    result = accept_all_autofixes(store, run_id)
    summary = summarize(store, run_id)
    return {**summary, **result, "findings": enrich_findings(store, run_id)}


@app.post("/api/runs/{run_id}/review/fixes/{fix_id}")
def review_fix(run_id: str, fix_id: str, body: FixReviewBody):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    if body.status not in {"accepted", "rejected"}:
        raise HTTPException(400, "status must be accepted|rejected")
    try:
        rec = apply_fix(store, run_id, fix_id, body.status)
    except KeyError:
        raise HTTPException(404, "Unknown fix")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"fix": rec, "findings": enrich_findings(store, run_id), **summarize(store, run_id)}


@app.get("/api/runs/{run_id}/export/workbook")
def export_workbook(run_id: str):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    data = workbook_bytes(store, run_id)
    run = store.get_run(run_id) or {}
    base = (run.get("filename") or "intellimap").rsplit(".", 1)[0]
    filename = _safe_filename(base, "reviewed", ext="xlsx")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=_attachment(filename),
    )


@app.get("/api/runs/{run_id}/frames")
def frames(run_id: str, type: str = Query(..., alias="type"), q: str = ""):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    return {"items": list_frames(store, run_id, type, q)}


@app.get("/api/runs/{run_id}/context")
def context(
    run_id: str,
    frame_type: str,
    frame_id: str,
    hops: int = 1,
    hide_unresolved: bool = False,
    view: str = "deterministic",
):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    graph = build_context(store, run_id, frame_type, frame_id, hops, hide_unresolved)
    if view == "ai_enhanced":
        graph = views_mod.enhance_graph(graph)
    elif view == "ai_abstract":
        graph = views_mod.abstract_graph(graph)
    graph["insights"] = store.insights(run_id, frame_type, frame_id)
    return graph


@app.post("/api/runs/{run_id}/ai/enhance")
def ai_enhance(run_id: str, body: FrameBody):
    graph = _require_graph(run_id, body)
    return views_mod.enhance_graph(graph)


@app.post("/api/runs/{run_id}/ai/abstract")
def ai_abstract(run_id: str, body: FrameBody):
    graph = _require_graph(run_id, body)
    return views_mod.abstract_graph(graph)


@app.post("/api/runs/{run_id}/ai/insights")
def ai_insights(run_id: str, body: FrameBody):
    graph = _require_graph(run_id, body)
    try:
        items = insights_mod.generate_insights(store, run_id, graph)
    except AIProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"items": items, "disclaimer": "Generated, not architecture ground truth."}


@app.post("/api/runs/{run_id}/ai/insights/{insight_id}")
def review_insight(run_id: str, insight_id: str, body: InsightReview):
    if body.status not in {"pending", "accepted", "rejected"}:
        raise HTTPException(400, "status must be pending|accepted|rejected")
    rec = store.set_insight_status(insight_id, body.status)
    if not rec or rec.get("run_id") != run_id:
        raise HTTPException(404, "Unknown insight")
    return rec


@app.post("/api/runs/{run_id}/chat")
def chat(run_id: str, body: ChatBody):
    graph = build_context(
        store, run_id, body.frame_type, body.frame_id, body.hops, body.hide_unresolved
    )
    try:
        result = chat_mod.chat(store, run_id, graph, body.messages, body.dropped)
    except AIProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    return result


@app.post("/api/runs/{run_id}/search")
def search_frame(run_id: str, body: SearchBody):
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    graph = build_context(
        store, run_id, body.frame_type, body.frame_id, body.hops, body.hide_unresolved
    )
    if body.mode == "text":
        return {"items": search_mod.text_search(graph, body.query), "mode": "text"}
    try:
        items = search_mod.semantic_search(graph, body.query)
    except AIProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"items": items, "mode": "ai"}


def _safe_filename(*parts: str, ext: str) -> str:
    raw = "-".join(str(p) for p in parts if p is not None and str(p) != "")
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in raw).strip("-._")
    return f"{safe or 'intellimap'}.{ext}"


def _attachment(filename: str) -> dict:
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
    }


@app.get("/api/runs/{run_id}/export/svg")
def export_svg(
    run_id: str,
    frame_type: str,
    frame_id: str,
    hops: int = 1,
    theme: str = "navy",
    view: str = "deterministic",
    hide_unresolved: bool = False,
):
    graph = _scoped_graph(run_id, frame_type, frame_id, hops, hide_unresolved, view)
    try:
        svg = render_svg(graph, theme=theme)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"SVG render failed: {exc}") from exc
    filename = _safe_filename("intellimap", frame_type, frame_id, theme, ext="svg")
    return Response(
        content=svg,
        media_type="image/svg+xml; charset=utf-8",
        headers=_attachment(filename),
    )


@app.get("/api/runs/{run_id}/export/json")
def export_json(
    run_id: str,
    frame_type: str,
    frame_id: str,
    hops: int = 1,
    view: str = "deterministic",
    hide_unresolved: bool = False,
):
    graph = _scoped_graph(run_id, frame_type, frame_id, hops, hide_unresolved, view)
    filename = _safe_filename("intellimap", frame_type, frame_id, ext="json")
    return JSONResponse(graph, headers=_attachment(filename))


@app.get("/api/runs/{run_id}/export/summary")
def export_summary(
    run_id: str,
    frame_type: str,
    frame_id: str,
    hops: int = 1,
    hide_unresolved: bool = False,
):
    graph = _scoped_graph(run_id, frame_type, frame_id, hops, hide_unresolved, "deterministic")
    insights = [
        i
        for i in store.insights(run_id, frame_type, frame_id)
        if i.get("status") != "rejected"
    ]
    md = _summary_markdown(graph, insights)
    filename = _safe_filename("intellimap", frame_type, frame_id, ext="md")
    return PlainTextResponse(
        md,
        media_type="text/markdown; charset=utf-8",
        headers=_attachment(filename),
    )


@app.get("/api/themes")
def themes():
    return {"items": available_themes()}


def _require_graph(run_id: str, body: FrameBody) -> dict:
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    return build_context(
        store, run_id, body.frame_type, body.frame_id, body.hops, body.hide_unresolved
    )


def _scoped_graph(
    run_id: str,
    frame_type: str,
    frame_id: str,
    hops: int,
    hide_unresolved: bool,
    view: str,
) -> dict:
    if not store.get_run(run_id):
        raise HTTPException(404, "Unknown run")
    if not frame_id:
        raise HTTPException(400, "Pick a frame before exporting")
    graph = build_context(store, run_id, frame_type, frame_id, hops, hide_unresolved)
    try:
        if view == "ai_enhanced":
            return views_mod.enhance_graph(graph)
        if view == "ai_abstract":
            return views_mod.abstract_graph(graph)
    except AIProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    return graph


def _summary_markdown(graph: dict, insights: list[dict]) -> str:
    frame = graph.get("frame") or {}
    lines = [
        f"# IntelliMap summary — {frame.get('type')} `{frame.get('id')}`",
        "",
        "This document separates **source facts**, **deterministic findings**, and **AI-generated interpretation**.",
        "AI content is not architecture ground truth.",
        "",
        "## Frame",
        f"- Type: {frame.get('type')}",
        f"- ID: {frame.get('id')}",
        f"- Hops: {frame.get('hops')}",
        f"- Nodes: {(graph.get('stats') or {}).get('nodes')}",
        f"- Edges: {(graph.get('stats') or {}).get('edges')}",
        "",
        "## Nodes",
    ]
    for n in graph.get("nodes") or []:
        d = n.get("data") or {}
        src = ""
        if d.get("source_row"):
            src = f" ← {d.get('source_sheet')} row {d.get('source_row')}"
        flags = []
        if d.get("unresolved"):
            flags.append("unresolved")
        if d.get("sensitive"):
            flags.append("sensitive")
        flag_txt = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"- `{n['id']}` {d.get('label')} ({d.get('kind')}){flag_txt}{src}")
    lines += ["", "## Edges"]
    for e in graph.get("edges") or []:
        data = e.get("data") or {}
        src = f" ← {data.get('source_sheet')} row {data.get('source_row')}" if data.get("source_row") else ""
        lines.append(f"- `{e.get('id')}` {e.get('kind')} `{e.get('source')}` → `{e.get('target')}` {e.get('label') or ''}{src}")
    lines += ["", "## Deterministic findings"]
    if not graph.get("findings"):
        lines.append("- None in this frame.")
    for f in graph.get("findings") or []:
        loc = f"{f.get('source_sheet')} row {f.get('source_row')}" if f.get("source_row") else "derived"
        lines.append(f"- **{f.get('severity')}** `{f.get('rule_id')}` {f.get('title')} ({loc})")
        if f.get("description"):
            lines.append(f"  - {f['description']}")
    lines += ["", "## AI insights (accepted or pending; rejected omitted)"]
    if not insights:
        lines.append("- None.")
    for i in insights:
        lines.append(f"- **{i.get('title')}** _{i.get('status')}_")
        lines.append(f"  - {i.get('body')}")
        if i.get("related_ids"):
            lines.append(f"  - Related: {', '.join(f'`{x}`' for x in i['related_ids'])}")
    lines += ["", "---", "Generated by IntelliMap. Decision support only."]
    return "\n".join(lines) + "\n"


@app.exception_handler(AIProviderError)
async def ai_error(_, exc: AIProviderError):
    return JSONResponse({"detail": str(exc)}, status_code=503)
