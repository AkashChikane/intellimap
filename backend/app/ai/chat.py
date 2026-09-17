from __future__ import annotations

import json

from .insights import _known_ids, _safe_payload
from .provider import complete_json


SYSTEM = """You are IntelliMap, an architecture assistant grounded in one observation frame.
Answer only from the provided scoped graph facts and deterministic findings.
Never invent relationships or IDs.

Return JSON:
{
  "answer": "short markdown. First line must be Facts, Findings, or Interpretation.",
  "actions": [
    {"type": "focus_node", "node_id": "existing id", "label": "str"},
    {"type": "highlight_nodes", "node_ids": ["existing ids"], "label": "str"},
    {"type": "set_hops", "hops": 1,
     "label": "str"},
    {"type": "set_view", "view": "deterministic|ai_enhanced|ai_abstract", "label": "str"},
    {"type": "hide_unresolved", "value": true, "label": "str"}
  ],
  "cards": [
    {"type": "node", "id": "existing id", "label": "str", "kind": "str"},
    {"type": "finding", "title": "str", "severity": "str", "id": "str"}
  ]
}

When the user asks to look at, find, focus, or go to an application, include focus_node.
When they ask to hide unresolved, change hops, or switch view, include that action.
When listing apps, include node cards (max 5).
If dropped nodes are present, treat them as the focus.
Keep answer concise. Actions and cards are optional. Only existing IDs.
"""

ALLOWED_ACTIONS = {"focus_node", "highlight_nodes", "set_hops", "set_view", "hide_unresolved"}
ALLOWED_VIEWS = {"deterministic", "ai_enhanced", "ai_abstract"}


def chat(graph: dict, messages: list[dict], dropped: list[dict]) -> dict:
    payload = {
        "graph": _safe_payload(graph),
        "dropped_nodes": dropped,
        "conversation": messages[-12:],
    }
    data = complete_json(SYSTEM, json.dumps(payload, indent=2)[:16000])
    known = _known_ids(graph)
    answer = (data.get("answer") or "").strip() or "I cannot confirm that from this frame."
    actions = []
    for raw in data.get("actions") or []:
        cleaned = _clean_action(raw, known)
        if cleaned:
            actions.append(cleaned)
    cards = []
    for raw in data.get("cards") or []:
        cleaned = _clean_card(raw, known, graph)
        if cleaned:
            cards.append(cleaned)
    return {
        "answer": answer,
        "layer": "ai",
        "disclaimer": "Generated, not architecture ground truth.",
        "actions": actions,
        "cards": cards,
    }


def _clean_action(raw: dict, known: set[str]) -> dict | None:
    kind = (raw or {}).get("type")
    if kind not in ALLOWED_ACTIONS:
        return None
    if kind == "focus_node":
        nid = raw.get("node_id")
        if nid not in known:
            return None
        return {"type": kind, "node_id": nid, "label": raw.get("label") or nid}
    if kind == "highlight_nodes":
        ids = [i for i in (raw.get("node_ids") or []) if i in known][:8]
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
    return None


def _clean_card(raw: dict, known: set[str], graph: dict) -> dict | None:
    kind = (raw or {}).get("type")
    if kind == "node":
        nid = raw.get("id")
        if nid not in known:
            return None
        node = next((n for n in graph.get("nodes") or [] if n.get("id") == nid), None)
        data = (node or {}).get("data") or {}
        return {
            "type": "node",
            "id": nid,
            "label": raw.get("label") or data.get("label") or nid,
            "kind": data.get("kind") or raw.get("kind"),
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
