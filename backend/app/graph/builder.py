from __future__ import annotations

from collections import defaultdict, deque

from ..config import SENSITIVE_CLASSIFICATIONS
from ..db.store import Store
from .analysis import directed_pairs
from .layout import layout_nodes


def list_frames(store: Store, run_id: str, frame_type: str, q: str = "") -> list[dict]:
    needle = (q or "").strip().lower()
    items = []
    if frame_type == "application":
        for app in store.applications(run_id):
            items.append(
                {
                    "id": app["application_id"],
                    "label": app.get("application_name") or app["application_id"],
                    "secondary": app.get("business_domain") or "",
                    "type": "application",
                }
            )
    elif frame_type == "business_process":
        seen = set()
        for proc in store.processes(run_id):
            pid = proc.get("business_process_id") or proc.get("process_mapping_id")
            if pid in seen:
                continue
            seen.add(pid)
            items.append(
                {
                    "id": pid,
                    "label": proc.get("business_process_name") or pid,
                    "secondary": proc.get("process_domain") or "",
                    "type": "business_process",
                }
            )
    elif frame_type == "domain":
        seen = set()
        for app in store.applications(run_id):
            domain = (app.get("business_domain") or "").strip()
            if not domain or domain in seen:
                continue
            seen.add(domain)
            items.append({"id": domain, "label": domain, "secondary": "Business domain", "type": "domain"})
    elif frame_type == "information_object":
        seen = set()
        for flow in store.flows(run_id):
            name = (flow.get("information_object") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            items.append(
                {
                    "id": name,
                    "label": name,
                    "secondary": flow.get("classification") or "",
                    "type": "information_object",
                }
            )
    else:
        return []
    if needle:
        items = [
            i
            for i in items
            if needle in i["id"].lower() or needle in i["label"].lower() or needle in (i["secondary"] or "").lower()
        ]
    return items


def build_context(
    store: Store,
    run_id: str,
    frame_type: str,
    frame_id: str,
    hops: int = 1,
    hide_unresolved: bool = False,
) -> dict:
    hops = max(1, min(int(hops or 1), 2))
    apps = {a["application_id"]: a for a in store.applications(run_id)}
    rels = store.relationships(run_id)
    ifaces = store.interfaces(run_id)
    flows = store.flows(run_id)
    procs = store.processes(run_id)
    owners = store.ownership(run_id)
    findings = store.findings(run_id)

    neighbors = _adjacency(rels, ifaces, flows)
    seed_apps, extra_nodes, boundary = _seeds(frame_type, frame_id, apps, procs, flows)
    scoped_apps = _expand(seed_apps, neighbors, hops)
    if frame_type == "domain":
        scoped_apps, boundary = _domain_scope(frame_id, apps, neighbors)
    if frame_type == "business_process":
        scoped_apps, boundary = _process_scope(frame_id, procs, neighbors, hops)
    if frame_type == "information_object":
        scoped_apps = set(seed_apps)

    nodes = []
    node_ids = set()
    for aid in scoped_apps:
        node = _app_node(aid, apps, owners, findings, seed=(aid in seed_apps), boundary=(aid in boundary))
        nodes.append(node)
        node_ids.add(aid)

    unresolved = set()
    edges = []

    def absorb_unresolved(end: str | None):
        if not end or end in node_ids:
            return end in node_ids
        if end in apps:
            return False
        unresolved.add(end)
        if hide_unresolved:
            return False
        nodes.append(_unresolved_node(end, findings))
        node_ids.add(end)
        return True

    def both_in_scope(src, tgt) -> bool:
        src_ok = src in node_ids or absorb_unresolved(src)
        tgt_ok = tgt in node_ids or absorb_unresolved(tgt)
        return src_ok and tgt_ok

    for rel in rels:
        src, tgt = rel.get("source_application_id"), rel.get("target_application_id")
        if both_in_scope(src, tgt):
            edges.append(_rel_edge(rel, src in boundary or tgt in boundary))

    for iface in ifaces:
        src, tgt = iface.get("provider_application_id"), iface.get("consumer_application_id")
        if both_in_scope(src, tgt):
            edges.append(_iface_edge(iface, src in boundary or tgt in boundary))

    scoped_flows = []
    for flow in flows:
        src, tgt = flow.get("source_application_id"), flow.get("target_application_id")
        if frame_type == "information_object":
            if (flow.get("information_object") or "") != frame_id:
                continue
        elif not (src in node_ids or tgt in node_ids):
            continue
        if not both_in_scope(src, tgt):
            continue
        if src in node_ids and tgt in node_ids:
            scoped_flows.append(flow)
            if frame_type == "information_object":
                if flow["flow_id"] not in node_ids:
                    nodes.append(_flow_node(flow))
                    node_ids.add(flow["flow_id"])
                edges.append(
                    {
                        "id": f"obj-{flow['flow_id']}-src",
                        "source": src,
                        "target": flow["flow_id"],
                        "kind": "flow",
                        "label": flow.get("operation") or "",
                        "data": {
                            "kind": "flow",
                            "source_sheet": "InformationObjects",
                            "source_row": flow["source_row"],
                            "id": flow["flow_id"],
                        },
                    }
                )
                edges.append(
                    {
                        "id": f"obj-{flow['flow_id']}-tgt",
                        "source": flow["flow_id"],
                        "target": tgt,
                        "kind": "flow",
                        "label": flow.get("classification") or "",
                        "data": {
                            "kind": "flow",
                            "source_sheet": "InformationObjects",
                            "source_row": flow["source_row"],
                            "id": flow["flow_id"],
                        },
                    }
                )
            else:
                edges.append(_flow_edge(flow))

    scoped_procs = []
    if frame_type == "business_process":
        scoped_procs = [p for p in procs if p.get("business_process_id") == frame_id]
        nodes.append(_process_node(frame_id, scoped_procs))
        node_ids.add(f"proc:{frame_id}")
        for p in scoped_procs:
            aid = p.get("supporting_application_id")
            if aid in node_ids:
                edges.append(
                    {
                        "id": f"sup-{p['process_mapping_id']}",
                        "source": aid,
                        "target": f"proc:{frame_id}",
                        "kind": "supports",
                        "label": p.get("role_of_application") or "supports",
                        "data": {
                            "kind": "supports",
                            "source_sheet": "BusinessProcesses",
                            "source_row": p["source_row"],
                            "id": p["process_mapping_id"],
                        },
                    }
                )
    else:
        for p in procs:
            if p.get("supporting_application_id") in seed_apps or (
                frame_type == "application" and p.get("supporting_application_id") == frame_id
            ):
                scoped_procs.append(p)
        # satellite process nodes for the selected application
        if frame_type == "application":
            by_proc = defaultdict(list)
            for p in scoped_procs:
                by_proc[p.get("business_process_id")].append(p)
            for pid, group in by_proc.items():
                nid = f"proc:{pid}"
                if nid not in node_ids:
                    nodes.append(_process_node(pid, group))
                    node_ids.add(nid)
                edges.append(
                    {
                        "id": f"sup-{frame_id}-{pid}",
                        "source": frame_id,
                        "target": nid,
                        "kind": "supports",
                        "label": group[0].get("role_of_application") or "supports",
                        "data": {
                            "kind": "supports",
                            "source_sheet": "BusinessProcesses",
                            "source_row": group[0]["source_row"],
                        },
                    }
                )

    related_ids = set(node_ids)
    scoped_findings = [
        f
        for f in findings
        if (f.get("entity_id") in related_ids)
        or (f.get("related_application_id") in related_ids)
        or (f.get("entity_id") in {p.get("process_mapping_id") for p in scoped_procs})
        or (f.get("entity_id") in {fl["flow_id"] for fl in scoped_flows})
        or (f.get("extra") or {}).get("unresolved_id") in related_ids
    ]

    layout_nodes(nodes, edges, focus_id=_focus_id(frame_type, frame_id))
    facts = {
        "applications": [apps[a] for a in scoped_apps if a in apps],
        "ownership": [o for o in owners if o.get("application_id") in node_ids],
        "relationships": [e["data"] for e in edges if e.get("kind") == "relationship"],
        "interfaces": [e["data"] for e in edges if e.get("kind") == "interface"],
        "flows": scoped_flows,
        "processes": scoped_procs,
    }
    return {
        "frame": {"type": frame_type, "id": frame_id, "hops": hops},
        "view": "deterministic",
        "nodes": nodes,
        "edges": edges,
        "findings": scoped_findings,
        "facts": facts,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "unresolved": len(unresolved),
            "findings": len(scoped_findings),
        },
    }


def _focus_id(frame_type: str, frame_id: str) -> str:
    if frame_type == "business_process":
        return f"proc:{frame_id}"
    return frame_id


def _adjacency(rels, ifaces, flows):
    adj = defaultdict(set)
    for src, tgt, _rel in directed_pairs(rels):
        adj[src].add(tgt)
        adj[tgt].add(src)
    for iface in ifaces:
        a, b = iface.get("provider_application_id"), iface.get("consumer_application_id")
        if a and b:
            adj[a].add(b)
            adj[b].add(a)
    for flow in flows:
        a, b = flow.get("source_application_id"), flow.get("target_application_id")
        if a and b:
            adj[a].add(b)
            adj[b].add(a)
    return adj


def _expand(seeds: set[str], adj, hops: int) -> set[str]:
    seen = set(seeds)
    q = deque((s, 0) for s in seeds)
    while q:
        node, dist = q.popleft()
        if dist >= hops:
            continue
        for nxt in adj.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, dist + 1))
    return seen


def _seeds(frame_type, frame_id, apps, procs, flows):
    extra = []
    boundary = set()
    if frame_type == "application":
        return {frame_id}, extra, boundary
    if frame_type == "domain":
        seeds = {a for a, rec in apps.items() if rec.get("business_domain") == frame_id}
        return seeds, extra, boundary
    if frame_type == "business_process":
        seeds = {
            p.get("supporting_application_id")
            for p in procs
            if p.get("business_process_id") == frame_id and p.get("supporting_application_id")
        }
        return seeds, extra, boundary
    if frame_type == "information_object":
        seeds = set()
        for flow in flows:
            if flow.get("information_object") == frame_id:
                if flow.get("source_application_id"):
                    seeds.add(flow["source_application_id"])
                if flow.get("target_application_id"):
                    seeds.add(flow["target_application_id"])
        return seeds, extra, boundary
    return set(), extra, boundary


def _domain_scope(domain, apps, adj):
    internal = {aid for aid, rec in apps.items() if rec.get("business_domain") == domain}
    boundary = set()
    for aid in list(internal):
        for nxt in adj.get(aid, ()):
            if nxt not in internal:
                boundary.add(nxt)
    return internal | boundary, boundary


def _process_scope(process_id, procs, adj, hops):
    internal = {
        p.get("supporting_application_id")
        for p in procs
        if p.get("business_process_id") == process_id and p.get("supporting_application_id")
    }
    scoped = _expand(internal, adj, 1 if hops else 1)
    boundary = scoped - internal
    return scoped, boundary


def _risks_for(entity_id: str, findings: list[dict]) -> list[str]:
    flags = []
    for f in findings:
        if f.get("entity_id") == entity_id or f.get("related_application_id") == entity_id:
            flags.append(f["rule_id"])
    return sorted(set(flags))


def _app_node(aid, apps, owners, findings, seed=False, boundary=False) -> dict:
    rec = apps.get(aid)
    owner = next((o for o in owners if o.get("application_id") == aid), None)
    if not rec:
        return _unresolved_node(aid, findings)
    sensitive = any(
        f["rule_id"] == "sensitive_flow" and f.get("related_application_id") == aid for f in findings
    )
    return {
        "id": aid,
        "type": "application",
        "position": {"x": 0, "y": 0},
        "data": {
            "kind": "application",
            "label": rec.get("application_name") or aid,
            "id": aid,
            "domain": rec.get("business_domain"),
            "criticality": rec.get("business_criticality"),
            "lifecycle": rec.get("lifecycle_status"),
            "hosting": rec.get("hosting"),
            "owner": (owner or {}).get("application_owner"),
            "seed": seed,
            "boundary": boundary,
            "unresolved": False,
            "sensitive": sensitive,
            "risks": _risks_for(aid, findings),
            "source_sheet": "Applications",
            "source_row": rec.get("source_row"),
            "record": rec,
            "ownership": owner,
        },
    }


def _unresolved_node(aid: str, findings: list[dict]) -> dict:
    return {
        "id": aid,
        "type": "unresolved",
        "position": {"x": 0, "y": 0},
        "data": {
            "kind": "unresolved",
            "label": aid,
            "id": aid,
            "domain": None,
            "unresolved": True,
            "seed": False,
            "boundary": False,
            "sensitive": False,
            "risks": _risks_for(aid, findings) or ["unresolved_fk"],
            "source_sheet": None,
            "source_row": None,
            "record": None,
        },
    }


def _process_node(pid: str, group: list[dict]) -> dict:
    name = (group[0].get("business_process_name") if group else pid) or pid
    return {
        "id": f"proc:{pid}",
        "type": "process",
        "position": {"x": 0, "y": 0},
        "data": {
            "kind": "process",
            "label": name,
            "id": pid,
            "domain": group[0].get("process_domain") if group else "",
            "criticality": group[0].get("process_criticality") if group else "",
            "unresolved": False,
            "seed": False,
            "boundary": False,
            "sensitive": False,
            "risks": [],
            "source_sheet": "BusinessProcesses",
            "source_row": group[0]["source_row"] if group else None,
            "record": {"mappings": group},
        },
    }


def _flow_node(flow: dict) -> dict:
    clas = flow.get("classification") or ""
    return {
        "id": flow["flow_id"],
        "type": "information",
        "position": {"x": 0, "y": 0},
        "data": {
            "kind": "information_object",
            "label": flow.get("information_object") or flow["flow_id"],
            "id": flow["flow_id"],
            "classification": clas,
            "sensitive": clas.lower() in SENSITIVE_CLASSIFICATIONS,
            "unresolved": False,
            "seed": True,
            "boundary": False,
            "risks": [],
            "source_sheet": "InformationObjects",
            "source_row": flow.get("source_row"),
            "record": flow,
        },
    }


def _rel_edge(rel, boundary=False) -> dict:
    return {
        "id": rel["relationship_id"],
        "source": rel.get("source_application_id"),
        "target": rel.get("target_application_id"),
        "kind": "relationship",
        "label": rel.get("relationship_type") or "depends_on",
        "data": {
            **rel,
            "kind": "relationship",
            "boundary": boundary,
            "source_sheet": "Relationships",
        },
    }


def _iface_edge(iface, boundary=False) -> dict:
    return {
        "id": iface["interface_id"],
        "source": iface.get("provider_application_id"),
        "target": iface.get("consumer_application_id"),
        "kind": "interface",
        "label": iface.get("interface_name") or iface.get("protocol") or "interface",
        "data": {
            **iface,
            "kind": "interface",
            "boundary": boundary,
            "source_sheet": "Interfaces",
        },
    }


def _flow_edge(flow) -> dict:
    clas = flow.get("classification") or ""
    return {
        "id": flow["flow_id"],
        "source": flow.get("source_application_id"),
        "target": flow.get("target_application_id"),
        "kind": "flow",
        "label": flow.get("information_object") or "flow",
        "data": {
            **flow,
            "kind": "flow",
            "sensitive": clas.lower() in SENSITIVE_CLASSIFICATIONS,
            "source_sheet": "InformationObjects",
        },
    }
