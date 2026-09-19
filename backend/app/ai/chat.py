from __future__ import annotations

import json

from ..db.store import Store
from ..graph.analysis import directed_pairs
from .insights import _known_ids, _safe_payload
from .provider import complete_json


SYSTEM = """You are IntelliMap, an architecture assistant.

You receive:
- graph: the CURRENT scoped diagram (nodes actually drawn).
- landscape: applications and directed Relationships from the workbook, including rows that are NOT drawn at the current hops/frame.
- dropped_nodes: optional pins. If empty, the user is asking about the WHOLE current diagram (and may ask about off-canvas relationships). If present, treat them as extra focus unless they clearly ask about the whole diagram.

Rules:
- Never invent relationships or IDs.
- You MAY cite landscape.relationships even when in_diagram is false. Say that the link exists in Relationships but is not on the current diagram.
- If they ask about an application that is in landscape.applications but not on the graph, answer from landscape and include open_frame so they can switch the diagram.
- First line of answer must be Facts, Findings, or Interpretation.

Return JSON:
{
  "answer": "short markdown",
  "actions": [
    {"type": "focus_node", "node_id": "id on the current diagram", "label": "str"},
    {"type": "highlight_nodes", "node_ids": ["ids on the current diagram"], "label": "str"},
    {"type": "set_hops", "hops": 1, "label": "str"},
    {"type": "set_view", "view": "deterministic|ai_enhanced|ai_abstract", "label": "str"},
    {"type": "hide_unresolved", "value": true, "label": "str"},
    {"type": "open_frame", "frame_type": "application", "frame_id": "existing application id", "label": "str"}
  ],
  "cards": [
    {"type": "node", "id": "existing id", "label": "str", "kind": "str"},
    {"type": "finding", "title": "str", "severity": "str", "id": "str"}
  ]
}

focus_node / highlight_nodes only for IDs on the current graph.
open_frame for an application that exists in the landscape but may not be drawn.
When listing apps, include node cards (max 5).
Keep answer concise. Actions and cards are optional.
"""

ALLOWED_ACTIONS = {
    "focus_node",
    "highlight_nodes",
    "set_hops",
    "set_view",
    "hide_unresolved",
    "open_frame",
}
ALLOWED_VIEWS = {"deterministic", "ai_enhanced", "ai_abstract"}
ALLOWED_FRAMES = {"application", "business_process", "domain", "information_object"}


def chat(
    store: Store,
    run_id: str,
    graph: dict,
    messages: list[dict],
    dropped: list[dict],
) -> dict:
    landscape = landscape_index(store, run_id, graph)
    payload = {
        "graph": _safe_payload(graph),
        "landscape": landscape,
        "dropped_nodes": dropped or [],
        "conversation": messages[-12:],
    }
    data = complete_json(SYSTEM, json.dumps(payload, separators=(",", ":"))[:24000])
    drawn = _known_ids(graph)
    catalog = {row["id"] for row in landscape.get("applications") or []}
    known = drawn | catalog
    answer = (data.get("answer") or "").strip() or "I cannot confirm that from this frame or the Relationships sheet."
    actions = []
    for raw in data.get("actions") or []:
        cleaned = _clean_action(raw, drawn, catalog)
        if cleaned:
            actions.append(cleaned)
    cards = []
    for raw in data.get("cards") or []:
        cleaned = _clean_card(raw, known, graph, landscape)
        if cleaned:
            cards.append(cleaned)
    return {
        "answer": answer,
        "layer": "ai",
        "disclaimer": "Generated, not architecture ground truth.",
        "actions": actions,
        "cards": cards,
    }


def landscape_index(store: Store, run_id: str, graph: dict, rel_limit: int = 220) -> dict:
    in_diagram = _known_ids(graph)
    apps = store.applications(run_id)
    names = {
        (a.get("application_id") or "").strip(): (a.get("application_name") or a.get("application_id") or "").strip()
        for a in apps
        if a.get("application_id")
    }
    app_rows = []
    for app in apps:
        aid = (app.get("application_id") or "").strip()
        if not aid:
            continue
        app_rows.append(
            {
                "id": aid,
                "name": names.get(aid) or aid,
                "domain": app.get("business_domain") or "",
                "lifecycle": app.get("lifecycle_status") or "",
                "in_diagram": aid in in_diagram,
            }
        )

    rels = []
    for src, tgt, rel in directed_pairs(store.relationships(run_id)):
        if not src or not tgt:
            continue
        rels.append(
            {
                "source": src,
                "source_name": names.get(src, src),
                "target": tgt,
                "target_name": names.get(tgt, tgt),
                "type": rel.get("relationship_type") or "depends_on",
                "criticality": rel.get("dependency_criticality") or "",
                "in_diagram": src in in_diagram and tgt in in_diagram,
            }
        )

    def score(row: dict) -> tuple[int, str]:
        touch = row["source"] in in_diagram or row["target"] in in_diagram
        if touch and not row["in_diagram"]:
            return (0, row["source"])
        if row["in_diagram"]:
            return (1, row["source"])
        return (2, row["source"])

    rels.sort(key=score)
    truncated = len(rels) > rel_limit
    rels = rels[:rel_limit]

    keep_ids = set(in_diagram)
    for row in rels:
        keep_ids.add(row["source"])
        keep_ids.add(row["target"])
    app_limit = 180
    preferred = [a for a in app_rows if a["id"] in keep_ids]
    rest = [a for a in app_rows if a["id"] not in keep_ids]
    app_rows = (preferred + rest)[:app_limit]

    return {
        "applications": app_rows,
        "relationships": rels,
        "truncated": truncated,
        "note": (
            "relationships are source facts from the Relationships sheet. "
            "in_diagram=false means the edge exists in the workbook but is not drawn at the current hops/frame."
        ),
    }


def _clean_action(raw: dict, drawn: set[str], catalog: set[str]) -> dict | None:
    kind = (raw or {}).get("type")
    if kind not in ALLOWED_ACTIONS:
        return None
    if kind == "focus_node":
        nid = raw.get("node_id")
        if nid not in drawn:
            return None
        return {"type": kind, "node_id": nid, "label": raw.get("label") or nid}
    if kind == "highlight_nodes":
        ids = [i for i in (raw.get("node_ids") or []) if i in drawn][:8]
        if not ids:
            return None
        return {"type": kind, "node_ids": ids, "label": raw.get("label") or "Highlight"}
    if kind == "set_hops":
        hops = raw.get("hops")
        try:
            hops = int(hops)
        except (TypeError, ValueError):
            return None
        if hops not in (1, 2):
            return None
        return {"type": kind, "hops": hops, "label": raw.get("label") or f"{hops} hop"}
    if kind == "set_view":
        view = raw.get("view")
        if view not in ALLOWED_VIEWS:
            return None
        return {"type": kind, "view": view, "label": raw.get("label") or view}
    if kind == "hide_unresolved":
        return {
            "type": kind,
            "value": bool(raw.get("value")),
            "label": raw.get("label") or "Hide unresolved",
        }
    if kind == "open_frame":
        fid = raw.get("frame_id")
        ftype = raw.get("frame_type") or "application"
        if ftype not in ALLOWED_FRAMES:
            return None
        if ftype == "application" and fid not in catalog:
            return None
        if not fid:
            return None
        return {
            "type": kind,
            "frame_type": ftype,
            "frame_id": fid,
            "label": raw.get("label") or fid,
        }
    return None


def _clean_card(raw: dict, known: set[str], graph: dict, landscape: dict) -> dict | None:
    kind = (raw or {}).get("type")
    if kind == "node":
        nid = raw.get("id")
        if nid not in known:
            return None
        node = next((n for n in graph.get("nodes") or [] if n.get("id") == nid), None)
        data = (node or {}).get("data") or {}
        land = next((a for a in (landscape.get("applications") or []) if a.get("id") == nid), None)
        return {
            "type": "node",
            "id": nid,
            "label": raw.get("label") or data.get("label") or (land or {}).get("name") or nid,
            "kind": data.get("kind") or raw.get("kind") or "application",
        }
    if kind == "finding":
        title = (raw.get("title") or "").strip()
        if not title:
            return None
        return {
            "type": "finding",
            "id": raw.get("id"),
            "title": title,
            "severity": raw.get("severity") or "quality",
        }
    return None
