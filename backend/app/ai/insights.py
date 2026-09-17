from __future__ import annotations

import json

from ..db.store import Store
from .provider import AIProviderError, complete_json, provider_name


SYSTEM = """You are IntelliMap, an enterprise-architecture assistant.
You receive SOURCE FACTS and DETERMINISTIC FINDINGS derived from a workbook.
You must NOT invent applications, relationships, interfaces, or flows.
Every insight must cite existing IDs from the payload.
Separate your interpretation from facts. If evidence is missing, say so.
Return JSON: {"insights":[{"title":str,"body":str,"related_ids":[str],"based_on_finding_ids":[str],"confidence":"low|medium|high"}]}
Max 5 insights. Body: 2-4 sentences. This is decision support, not ground truth.
"""


def generate_insights(store: Store, run_id: str, graph: dict) -> list[dict]:
    payload = _safe_payload(graph)
    data = complete_json(SYSTEM, json.dumps(payload, indent=2)[:14000])
    known_ids = _known_ids(graph)
    known_findings = {f["id"] for f in graph.get("findings") or []}
    saved = []
    for item in data.get("insights") or []:
        related = [i for i in (item.get("related_ids") or []) if i in known_ids]
        based = [i for i in (item.get("based_on_finding_ids") or []) if i in known_findings]
        if not item.get("title") or not item.get("body"):
            continue
        rec = store.add_insight(
            run_id,
            {
                "frame_type": (graph.get("frame") or {}).get("type"),
                "frame_id": (graph.get("frame") or {}).get("id"),
                "title": item.get("title"),
                "body": item.get("body"),
                "related_ids": related,
                "based_on_finding_ids": based,
                "confidence": item.get("confidence") or "medium",
            },
        )
        rec["layer"] = "ai"
        rec["provider"] = provider_name()
        saved.append(rec)
    return saved


def _known_ids(graph: dict) -> set[str]:
    ids = set()
    for n in graph.get("nodes") or []:
        ids.add(n["id"])
        if n.get("data", {}).get("id"):
            ids.add(n["data"]["id"])
    for e in graph.get("edges") or []:
        ids.add(e.get("id"))
        ids.add(e.get("source"))
        ids.add(e.get("target"))
    return {i for i in ids if i}


def _safe_payload(graph: dict) -> dict:
    nodes = []
    for n in graph.get("nodes") or []:
        d = n.get("data") or {}
        nodes.append(
            {
                "id": n.get("id"),
                "kind": d.get("kind"),
                "label": d.get("label"),
                "domain": d.get("domain"),
                "lifecycle": d.get("lifecycle"),
                "unresolved": d.get("unresolved"),
                "sensitive": d.get("sensitive"),
                "risks": d.get("risks"),
                "source_sheet": d.get("source_sheet"),
                "source_row": d.get("source_row"),
            }
        )
    edges = []
    for e in graph.get("edges") or []:
        edges.append(
            {
                "id": e.get("id"),
                "kind": e.get("kind"),
                "source": e.get("source"),
                "target": e.get("target"),
                "label": e.get("label"),
                "sensitive": (e.get("data") or {}).get("sensitive"),
            }
        )
    findings = [
        {
            "id": f.get("id"),
            "rule_id": f.get("rule_id"),
            "severity": f.get("severity"),
            "title": f.get("title"),
            "entity_id": f.get("entity_id"),
            "related_application_id": f.get("related_application_id"),
            "source_sheet": f.get("source_sheet"),
            "source_row": f.get("source_row"),
        }
        for f in graph.get("findings") or []
    ]
    return {
        "frame": graph.get("frame"),
        "nodes": nodes,
        "edges": edges,
        "findings": findings,
        "disclaimer": "Do not invent IDs. Facts come from the workbook; findings are deterministic.",
    }


def require_ai():
    from .provider import available

    if not available():
        raise AIProviderError("LLM is not configured")
