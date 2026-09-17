from __future__ import annotations

import json
from collections import defaultdict

from .insights import _known_ids, _safe_payload
from .provider import AIProviderError, available, complete_json


ENHANCE_SYSTEM = """You enhance an architecture context diagram without changing facts.
Return JSON:
{
  "groups": [{"id": "grp-domain", "label": str, "member_ids": [existing node ids]}],
  "emphasis": [existing node ids],
  "annotations": [{"id": existing node id, "note": str}]
}
Rules: only use IDs from the input. Do not add edges. Do not invent applications.
Groups should cluster by business domain or process role.
"""

ABSTRACT_SYSTEM = """You create a simplified abstract architecture view.
Keep the observation-frame node. Collapse other applications into domain groups.
Keep only critical, high-centrality, sensitive, or unresolved edges.
Return JSON:
{
  "keep_ids": [node ids to leave expanded],
  "groups": [{"id": "grp-x", "label": str, "member_ids": [node ids]}],
  "keep_edge_ids": [edge ids]
}
Use only IDs from the input. Never invent relationships.
"""


def enhance_graph(graph: dict) -> dict:
    known = _known_ids(graph)
    if available():
        try:
            spec = complete_json(ENHANCE_SYSTEM, json.dumps(_safe_payload(graph))[:14000])
        except AIProviderError:
            spec = _heuristic_enhance(graph)
    else:
        spec = _heuristic_enhance(graph)
    return apply_enhance(graph, spec, known)


def abstract_graph(graph: dict) -> dict:
    known = _known_ids(graph)
    if available():
        try:
            spec = complete_json(ABSTRACT_SYSTEM, json.dumps(_safe_payload(graph))[:14000])
        except AIProviderError:
            spec = _heuristic_abstract(graph)
    else:
        spec = _heuristic_abstract(graph)
    return apply_abstract(graph, spec, known)


def apply_enhance(graph: dict, spec: dict, known: set[str]) -> dict:
    nodes = list(graph.get("nodes") or [])
    by_id = {n["id"]: n for n in nodes}
    groups = []
    for g in spec.get("groups") or []:
        members = [m for m in (g.get("member_ids") or []) if m in by_id]
        if len(members) < 2:
            continue
        gid = str(g.get("id") or f"grp-{g.get('label')}").replace(" ", "-")
        if gid in by_id:
            continue
        xs = [by_id[m]["position"]["x"] for m in members]
        ys = [by_id[m]["position"]["y"] for m in members]
        group_node = {
            "id": gid,
            "type": "group",
            "position": {"x": min(xs) - 24, "y": min(ys) - 36},
            "style": {
                "width": max(xs) - min(xs) + 268,
                "height": max(ys) - min(ys) + 150,
            },
            "data": {
                "kind": "group",
                "label": g.get("label") or gid,
                "id": gid,
                "member_ids": members,
                "layer": "ai",
            },
        }
        groups.append(group_node)
        for m in members:
            by_id[m]["parentId"] = gid
            by_id[m]["extent"] = "parent"
            by_id[m]["position"] = {
                "x": by_id[m]["position"]["x"] - (min(xs) - 24),
                "y": by_id[m]["position"]["y"] - (min(ys) - 36),
            }
    emphasis = {i for i in (spec.get("emphasis") or []) if i in known}
    notes = {a["id"]: a.get("note") for a in (spec.get("annotations") or []) if a.get("id") in known}
    for n in nodes:
        if n["id"] in emphasis:
            n["data"]["emphasis"] = True
        if n["id"] in notes:
            n["data"]["ai_note"] = notes[n["id"]]
        n["data"]["layer"] = "source"
    out = dict(graph)
    out["nodes"] = groups + nodes
    out["view"] = "ai_enhanced"
    out["ai_meta"] = {"spec": spec, "invented_dropped": True}
    return out


def apply_abstract(graph: dict, spec: dict, known: set[str]) -> dict:
    keep = {i for i in (spec.get("keep_ids") or []) if i in known}
    frame = graph.get("frame") or {}
    focus = frame.get("id")
    if focus:
        keep.add(focus)
        keep.add(f"proc:{focus}")
    original_nodes = {n["id"]: n for n in graph.get("nodes") or []}
    groups_spec = spec.get("groups") or []
    new_nodes = []
    member_to_group = {}
    for g in groups_spec:
        members = [m for m in (g.get("member_ids") or []) if m in original_nodes and m not in keep]
        if len(members) < 2:
            continue
        gid = str(g.get("id") or f"grp-{g.get('label')}").replace(" ", "-")
        xs = [original_nodes[m]["position"]["x"] for m in members]
        ys = [original_nodes[m]["position"]["y"] for m in members]
        new_nodes.append(
            {
                "id": gid,
                "type": "groupNode",
                "position": {"x": sum(xs) / len(xs), "y": sum(ys) / len(ys)},
                "data": {
                    "kind": "group",
                    "label": g.get("label") or gid,
                    "id": gid,
                    "member_ids": members,
                    "member_count": len(members),
                    "layer": "ai",
                    "source_sheet": "derived",
                    "source_row": None,
                },
            }
        )
        for m in members:
            member_to_group[m] = gid

    for nid, node in original_nodes.items():
        if nid in keep or nid not in member_to_group:
            if nid in member_to_group:
                continue
            cloned = dict(node)
            cloned["data"] = dict(node.get("data") or {})
            cloned["data"]["layer"] = "source"
            new_nodes.append(cloned)

    keep_edges = set(spec.get("keep_edge_ids") or [])
    new_edges = []
    seen = set()
    for e in graph.get("edges") or []:
        src = member_to_group.get(e.get("source"), e.get("source"))
        tgt = member_to_group.get(e.get("target"), e.get("target"))
        if src == tgt:
            continue
        if keep_edges and e.get("id") not in keep_edges and src in original_nodes and tgt in original_nodes:
            # still keep if either end collapsed, so the group connection remains
            if e.get("source") not in member_to_group and e.get("target") not in member_to_group:
                continue
        key = (src, tgt, e.get("kind"))
        if key in seen:
            continue
        seen.add(key)
        new_edges.append(
            {
                **e,
                "id": f"abs-{e.get('id')}",
                "source": src,
                "target": tgt,
                "data": {**(e.get("data") or {}), "from_edge_id": e.get("id"), "layer": "ai"},
            }
        )
    out = dict(graph)
    out["nodes"] = new_nodes
    out["edges"] = new_edges
    out["view"] = "ai_abstract"
    out["ai_meta"] = {"spec": spec}
    from ..graph.layout import layout_nodes

    layout_nodes(out["nodes"], out["edges"], focus_id=focus)
    return out


def _heuristic_enhance(graph: dict) -> dict:
    groups = defaultdict(list)
    for n in graph.get("nodes") or []:
        if n.get("data", {}).get("kind") != "application":
            continue
        domain = n["data"].get("domain") or "Other"
        groups[domain].append(n["id"])
    spec_groups = []
    for domain, members in groups.items():
        if len(members) >= 2:
            spec_groups.append({"id": f"grp-{domain}", "label": domain, "member_ids": members})
    emphasis = [n["id"] for n in graph.get("nodes") or [] if n.get("data", {}).get("seed") or n.get("data", {}).get("unresolved")]
    annotations = []
    for n in graph.get("nodes") or []:
        if n.get("data", {}).get("unresolved"):
            annotations.append({"id": n["id"], "note": "Unresolved foreign key — not discarded."})
    return {"groups": spec_groups, "emphasis": emphasis, "annotations": annotations, "heuristic": True}


def _heuristic_abstract(graph: dict) -> dict:
    frame = graph.get("frame") or {}
    keep = [frame.get("id")] if frame.get("id") else []
    for n in graph.get("nodes") or []:
        if n.get("data", {}).get("unresolved") or n.get("data", {}).get("seed"):
            keep.append(n["id"])
    groups = defaultdict(list)
    for n in graph.get("nodes") or []:
        if n.get("data", {}).get("kind") != "application":
            continue
        if n["id"] in keep:
            continue
        groups[n["data"].get("domain") or "Other"].append(n["id"])
    spec_groups = [
        {"id": f"grp-{domain}", "label": f"{domain} ({len(members)})", "member_ids": members}
        for domain, members in groups.items()
        if members
    ]
    keep_edges = [
        e["id"]
        for e in graph.get("edges") or []
        if e.get("kind") in {"flow", "interface"}
        or (e.get("data") or {}).get("sensitive")
        or (e.get("data") or {}).get("dependency_criticality", "").lower() in {"high", "mission critical"}
    ]
    return {"keep_ids": keep, "groups": spec_groups, "keep_edge_ids": keep_edges, "heuristic": True}
