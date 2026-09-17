from __future__ import annotations

import json
import re

from .insights import _known_ids, _safe_payload
from .provider import AIProviderError, complete_json


SYSTEM = """You rank architecture-graph nodes for a search query.
Return JSON: {"matches":[{"id": existing node id, "reason": str, "score": number}]}
Rules:
- Only use IDs from the input nodes.
- Rank by semantic relevance to the query (name, domain, role, risks, findings).
- Max 8 matches. score is 0-1.
- Never invent applications or IDs.
"""


def semantic_search(graph: dict, query: str) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    known = _known_ids(graph)
    local = text_search(graph, q)
    try:
        data = complete_json(
            SYSTEM,
            json.dumps({"query": q, "graph": _safe_payload(graph)}, indent=2)[:14000],
        )
    except AIProviderError:
        return local
    ranked = []
    seen = set()
    for item in data.get("matches") or []:
        nid = item.get("id")
        if nid not in known or nid in seen:
            continue
        seen.add(nid)
        node = _node(graph, nid)
        ranked.append(
            {
                "id": nid,
                "label": (node.get("data") or {}).get("label") or nid,
                "kind": (node.get("data") or {}).get("kind"),
                "reason": item.get("reason") or "Semantic match",
                "score": item.get("score") if isinstance(item.get("score"), (int, float)) else 0.5,
                "source": "ai",
            }
        )
    if not ranked:
        return local
    return ranked[:8]


def text_search(graph: dict, query: str) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return []
    tokens = [t for t in re.split(r"\s+", q) if t]
    scored = []
    for n in graph.get("nodes") or []:
        data = n.get("data") or {}
        initials = "".join(w[:1] for w in str(data.get("label") or "").split() if w).lower()
        hay = " ".join(
            str(x or "")
            for x in [
                n.get("id"),
                data.get("id"),
                data.get("label"),
                data.get("kind"),
                data.get("domain"),
                data.get("lifecycle"),
                data.get("owner"),
                data.get("classification"),
                initials,
                " ".join(data.get("risks") or []),
            ]
        ).lower()
        if not all(t in hay for t in tokens):
            continue
        score = 1.0 if q in hay else 0.6
        if (n.get("id") or "").lower() == q or (data.get("label") or "").lower() == q:
            score = 1.2
        scored.append(
            {
                "id": n.get("id"),
                "label": data.get("label") or n.get("id"),
                "kind": data.get("kind"),
                "reason": "Text match in this frame",
                "score": score,
                "source": "text",
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:12]


def _node(graph: dict, nid: str) -> dict:
    for n in graph.get("nodes") or []:
        if n.get("id") == nid or (n.get("data") or {}).get("id") == nid:
            return n
    return {}
