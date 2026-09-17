from __future__ import annotations

import networkx as nx


def directed_pairs(relationships: list[dict]) -> list[tuple[str, str, dict]]:
    pairs = []
    for rel in relationships:
        src = (rel.get("source_application_id") or "").strip()
        tgt = (rel.get("target_application_id") or "").strip()
        if not src or not tgt:
            continue
        direction = (rel.get("direction") or "source_to_target").strip().lower().replace(" ", "")
        if direction in {"targettosource", "target_to_source", "incoming"}:
            pairs.append((tgt, src, rel))
        elif direction in {"bidirectional", "both"}:
            pairs.append((src, tgt, rel))
            pairs.append((tgt, src, rel))
        else:
            pairs.append((src, tgt, rel))
    return pairs


def build_nx(relationships: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    for src, tgt, rel in directed_pairs(relationships):
        g.add_edge(src, tgt, id=rel.get("relationship_id"), data=rel)
    return g


def cycles(graph: nx.DiGraph, limit: int = 12) -> list[list[str]]:
    found = []
    try:
        for cycle in nx.simple_cycles(graph):
            if len(cycle) >= 2:
                found.append(cycle)
            if len(found) >= limit:
                break
    except nx.NetworkXNoCycle:
        return []
    return found


def centrality(graph: nx.DiGraph, top_n: int = 8) -> list[dict]:
    if graph.number_of_nodes() == 0:
        return []
    try:
        scores = nx.betweenness_centrality(graph)
    except Exception:
        scores = {n: graph.degree(n) for n in graph.nodes}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    out = []
    for node, score in ranked:
        out.append(
            {
                "application_id": node,
                "betweenness": round(float(score), 4),
                "in_degree": int(graph.in_degree(node)) if node in graph else 0,
                "out_degree": int(graph.out_degree(node)) if node in graph else 0,
            }
        )
    return out
