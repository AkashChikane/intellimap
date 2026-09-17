from __future__ import annotations

from collections import defaultdict


COL_W = 280
ROW_H = 130
ORIGIN_X = 80
ORIGIN_Y = 80


def layout_nodes(nodes: list[dict], edges: list[dict], focus_id: str | None = None) -> None:
    kinds = {n["id"]: n["data"].get("kind") for n in nodes}
    incoming = defaultdict(set)
    outgoing = defaultdict(set)
    for e in edges:
        if e.get("kind") == "supports":
            continue
        if e.get("source") and e.get("target"):
            outgoing[e["source"]].add(e["target"])
            incoming[e["target"]].add(e["source"])

    focus = focus_id if focus_id in kinds else None
    if not focus:
        for n in nodes:
            if n["data"].get("seed"):
                focus = n["id"]
                break
    if not focus and nodes:
        focus = nodes[0]["id"]

    columns = {"upstream": [], "focus": [], "downstream": [], "process": [], "other": []}
    for n in nodes:
        kind = n["data"].get("kind")
        nid = n["id"]
        if kind == "process":
            columns["process"].append(n)
        elif nid == focus:
            columns["focus"].append(n)
        elif focus and nid in incoming.get(focus, set()):
            columns["upstream"].append(n)
        elif focus and nid in outgoing.get(focus, set()):
            columns["downstream"].append(n)
        else:
            columns["other"].append(n)

    # leftover apps that are only connected laterally sit in other; park them under downstream
    def _sort_key(n):
        return (
            0 if n["data"].get("seed") else 1,
            0 if not n["data"].get("unresolved") else 1,
            (n["data"].get("domain") or ""),
            n["data"].get("label") or n["id"],
        )

    for key in columns:
        columns[key].sort(key=_sort_key)

    col_index = {"upstream": 0, "focus": 1, "downstream": 2, "other": 3, "process": 1}
    used = {"upstream": 0, "focus": 0, "downstream": 0, "other": 0, "process": 0}

    # processes sit on a lower row under the focus column
    max_upper = max(
        len(columns["upstream"]),
        len(columns["focus"]),
        len(columns["downstream"]),
        len(columns["other"]),
        1,
    )
    for bucket, items in columns.items():
        for n in items:
            col = col_index[bucket]
            if bucket == "process":
                x = ORIGIN_X + COL_W * col
                y = ORIGIN_Y + ROW_H * (max_upper + used[bucket] + 1)
            else:
                x = ORIGIN_X + COL_W * col
                y = ORIGIN_Y + ROW_H * used[bucket]
            n["position"] = {"x": x, "y": y}
            n["data"]["column"] = bucket
            used[bucket] += 1
