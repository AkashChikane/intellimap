from __future__ import annotations

from datetime import datetime

from ..config import SENSITIVE_CLASSIFICATIONS
from ..db.store import Store
from ..graph.analysis import build_nx, centrality, cycles


def _parse_date(value: str):
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def _name_of(store: Store, run_id: str, app_id: str) -> str:
    app = store.application(run_id, app_id)
    return (app or {}).get("application_name") or ""


def run_rules(store: Store, run_id: str) -> None:
    apps = store.applications(run_id)
    app_ids = {a["application_id"] for a in apps}
    app_names = {a["application_id"]: a.get("application_name") or "" for a in apps}
    rels = store.relationships(run_id)
    ifaces = store.interfaces(run_id)
    flows = store.flows(run_id)
    procs = store.processes(run_id)
    owners = store.ownership(run_id)
    gaps = store.known_gaps(run_id)
    today = datetime.utcnow().date()

    _fk_and_names(store, run_id, app_ids, app_names, rels, ifaces, flows, procs, owners)
    _ownership(store, run_id, apps, owners)
    _lifecycle(store, run_id, apps, today)
    _interfaces_and_flows(store, run_id, ifaces, flows, app_ids)
    _graph_rules(store, run_id, apps, rels, ifaces, procs)
    _sensitive(store, run_id, flows)
    _known_gaps(store, run_id, gaps)
    _retired_on_critical_path(store, run_id, apps, rels, procs)
    store.commit()


def _fk_and_names(store, run_id, app_ids, app_names, rels, ifaces, flows, procs, owners):
    def check(eid, etype, sheet, row, fk, fk_name, related=None):
        if not fk:
            store.add_finding(
                run_id,
                rule_id="missing_fk",
                severity="blocker",
                title=f"Missing application reference on {etype} {eid}",
                description="An application ID field is empty. The row is kept and shown as incomplete.",
                entity_type=etype,
                entity_id=eid,
                related_application_id=related,
                source_sheet=sheet,
                source_row=row,
            )
            return
        if fk not in app_ids:
            store.add_finding(
                run_id,
                rule_id="unresolved_fk",
                severity="blocker",
                title=f"Unresolved application {fk}",
                description=f"{etype} {eid} references {fk}, which is not present in Applications. The reference is kept and rendered as an unresolved node.",
                entity_type=etype,
                entity_id=eid,
                related_application_id=fk,
                source_sheet=sheet,
                source_row=row,
                extra={"unresolved_id": fk},
            )
        elif fk_name and app_names.get(fk) and fk_name != app_names.get(fk):
            store.add_finding(
                run_id,
                rule_id="name_mismatch",
                severity="quality",
                title=f"Name mismatch for {fk}",
                description=f"{etype} {eid} labels {fk} as '{fk_name}' but Applications has '{app_names.get(fk)}'. IDs are authoritative.",
                entity_type=etype,
                entity_id=eid,
                related_application_id=fk,
                source_sheet=sheet,
                source_row=row,
                extra={"recorded_name": fk_name, "canonical_name": app_names.get(fk)},
            )

    for rel in rels:
        check(
            rel["relationship_id"],
            "Relationship",
            "Relationships",
            rel["source_row"],
            rel.get("source_application_id"),
            rel.get("source_application_name"),
            rel.get("source_application_id"),
        )
        check(
            rel["relationship_id"],
            "Relationship",
            "Relationships",
            rel["source_row"],
            rel.get("target_application_id"),
            rel.get("target_application_name"),
            rel.get("target_application_id"),
        )
    for iface in ifaces:
        check(
            iface["interface_id"],
            "Interface",
            "Interfaces",
            iface["source_row"],
            iface.get("provider_application_id"),
            iface.get("provider_application_name"),
            iface.get("provider_application_id"),
        )
        check(
            iface["interface_id"],
            "Interface",
            "Interfaces",
            iface["source_row"],
            iface.get("consumer_application_id"),
            iface.get("consumer_application_name"),
            iface.get("consumer_application_id"),
        )
    for flow in flows:
        check(
            flow["flow_id"],
            "InformationObject",
            "InformationObjects",
            flow["source_row"],
            flow.get("source_application_id"),
            flow.get("source_application_name"),
            flow.get("source_application_id"),
        )
        check(
            flow["flow_id"],
            "InformationObject",
            "InformationObjects",
            flow["source_row"],
            flow.get("target_application_id"),
            flow.get("target_application_name"),
            flow.get("target_application_id"),
        )
    for proc in procs:
        check(
            proc["process_mapping_id"],
            "BusinessProcess",
            "BusinessProcesses",
            proc["source_row"],
            proc.get("supporting_application_id"),
            proc.get("supporting_application_name"),
            proc.get("supporting_application_id"),
        )
    for own in owners:
        app_id = (own.get("application_id") or "").strip()
        if app_id and app_id not in app_ids:
            store.add_finding(
                run_id,
                rule_id="unresolved_fk",
                severity="blocker",
                title=f"Ownership row for unknown application {app_id}",
                description="ApplicationOwnership references an application that is not in Applications.",
                entity_type="Ownership",
                entity_id=own.get("ownership_id"),
                related_application_id=app_id,
                source_sheet="ApplicationOwnership",
                source_row=own["source_row"],
            )


def _ownership(store, run_id, apps, owners):
    by_app = {}
    for own in owners:
        aid = (own.get("application_id") or "").strip()
        if aid:
            by_app.setdefault(aid, []).append(own)
    for app in apps:
        rows = by_app.get(app["application_id"])
        if not rows:
            store.add_finding(
                run_id,
                rule_id="missing_ownership",
                severity="risk",
                title=f"No ownership record for {app['application_id']}",
                description="The application exists but ApplicationOwnership has no row. Ownership can be missing independently of the application record.",
                entity_type="Application",
                entity_id=app["application_id"],
                related_application_id=app["application_id"],
                source_sheet="Applications",
                source_row=app["source_row"],
            )
            continue
        for own in rows:
            if not (own.get("application_owner") or "").strip() and not (
                own.get("owner_employee_id") or ""
            ).strip():
                store.add_finding(
                    run_id,
                    rule_id="blank_owner",
                    severity="risk",
                    title=f"Ownership row has no owner for {app['application_id']}",
                    description="ApplicationOwnership exists but ApplicationOwner and OwnerEmployeeID are empty.",
                    entity_type="Ownership",
                    entity_id=own.get("ownership_id"),
                    related_application_id=app["application_id"],
                    source_sheet="ApplicationOwnership",
                    source_row=own["source_row"],
                )


def _lifecycle(store, run_id, apps, today):
    for app in apps:
        start = _parse_date(app.get("lifecycle_start_date"))
        end = _parse_date(app.get("lifecycle_end_date"))
        status = (app.get("lifecycle_status") or "").strip()
        if start and end and end < start:
            store.add_finding(
                run_id,
                rule_id="lifecycle_dates_inverted",
                severity="risk",
                title=f"Lifecycle end before start for {app['application_id']}",
                description=f"LifecycleStartDate {app.get('lifecycle_start_date')} is after LifecycleEndDate {app.get('lifecycle_end_date')}.",
                entity_type="Application",
                entity_id=app["application_id"],
                related_application_id=app["application_id"],
                source_sheet="Applications",
                source_row=app["source_row"],
            )
        if end and end < today and status.lower() in {"active", "production", "live"}:
            store.add_finding(
                run_id,
                rule_id="active_past_end",
                severity="risk",
                title=f"{app['application_id']} is Active past its end date",
                description=f"LifecycleStatus is {status} but LifecycleEndDate is {app.get('lifecycle_end_date')}.",
                entity_type="Application",
                entity_id=app["application_id"],
                related_application_id=app["application_id"],
                source_sheet="Applications",
                source_row=app["source_row"],
            )
        if status.lower() in {"retired", "decommissioned", "sunset"} and not end:
            store.add_finding(
                run_id,
                rule_id="retired_without_end",
                severity="quality",
                title=f"{app['application_id']} is {status} without an end date",
                description="Retired applications should carry a LifecycleEndDate.",
                entity_type="Application",
                entity_id=app["application_id"],
                related_application_id=app["application_id"],
                source_sheet="Applications",
                source_row=app["source_row"],
            )


def _interfaces_and_flows(store, run_id, ifaces, flows, app_ids):
    iface_ids = {i["interface_id"] for i in ifaces}
    flows_by_iface = {}
    for flow in flows:
        iid = (flow.get("interface_id") or "").strip()
        if iid:
            flows_by_iface.setdefault(iid, []).append(flow)
        elif iid == "":
            store.add_finding(
                run_id,
                rule_id="flow_without_interface",
                severity="quality",
                title=f"Flow {flow['flow_id']} has no InterfaceID",
                description="Information flow is stored, but it is not linked to an interface.",
                entity_type="InformationObject",
                entity_id=flow["flow_id"],
                related_application_id=flow.get("source_application_id"),
                source_sheet="InformationObjects",
                source_row=flow["source_row"],
            )
        if iid and iid not in iface_ids:
            store.add_finding(
                run_id,
                rule_id="unresolved_interface",
                severity="blocker",
                title=f"Flow {flow['flow_id']} references missing interface {iid}",
                description="InformationObjects.InterfaceID does not match any Interfaces.InterfaceID. The flow is kept.",
                entity_type="InformationObject",
                entity_id=flow["flow_id"],
                related_application_id=flow.get("source_application_id"),
                source_sheet="InformationObjects",
                source_row=flow["source_row"],
                extra={"interface_id": iid},
            )
    for iface in ifaces:
        if iface["interface_id"] not in flows_by_iface:
            store.add_finding(
                run_id,
                rule_id="orphan_interface",
                severity="quality",
                title=f"Interface {iface['interface_id']} has no information flows",
                description="The interface exists but no InformationObjects row points at it.",
                entity_type="Interface",
                entity_id=iface["interface_id"],
                related_application_id=iface.get("provider_application_id"),
                source_sheet="Interfaces",
                source_row=iface["source_row"],
            )


def _graph_rules(store, run_id, apps, rels, ifaces, procs):
    graph = build_nx(rels)
    for cycle in cycles(graph):
        store.add_finding(
            run_id,
            rule_id="dependency_cycle",
            severity="risk",
            title="Directed dependency cycle",
            description=" → ".join(cycle + [cycle[0]]),
            entity_type="Relationship",
            entity_id=cycle[0],
            related_application_id=cycle[0],
            source_sheet="Relationships",
            source_row=None,
            extra={"cycle": cycle},
        )
    for item in centrality(graph):
        if item["betweenness"] <= 0:
            continue
        if item["in_degree"] + item["out_degree"] >= 6:
            app = store.application(run_id, item["application_id"])
            store.add_finding(
                run_id,
                rule_id="high_centrality",
                severity="quality",
                title=f"{item['application_id']} is a concentration point",
                description=f"Betweenness {item['betweenness']}, in-degree {item['in_degree']}, out-degree {item['out_degree']}. Concentration is a risk lens, not a defect.",
                entity_type="Application",
                entity_id=item["application_id"],
                related_application_id=item["application_id"],
                source_sheet="Applications",
                source_row=(app or {}).get("source_row"),
                extra=item,
            )

    rel_apps = set()
    for rel in rels:
        rel_apps.add(rel.get("source_application_id"))
        rel_apps.add(rel.get("target_application_id"))
    iface_apps = set()
    for iface in ifaces:
        iface_apps.add(iface.get("provider_application_id"))
        iface_apps.add(iface.get("consumer_application_id"))
    proc_apps = {p.get("supporting_application_id") for p in procs}
    for app in apps:
        aid = app["application_id"]
        if aid not in rel_apps:
            store.add_finding(
                run_id,
                rule_id="no_relationships",
                severity="quality",
                title=f"{aid} has no relationships",
                description="Anti-join: application does not appear as source or target in Relationships.",
                entity_type="Application",
                entity_id=aid,
                related_application_id=aid,
                source_sheet="Applications",
                source_row=app["source_row"],
            )
        if aid not in iface_apps:
            store.add_finding(
                run_id,
                rule_id="no_interfaces",
                severity="quality",
                title=f"{aid} has no interfaces",
                description="Anti-join: application is neither provider nor consumer on Interfaces.",
                entity_type="Application",
                entity_id=aid,
                related_application_id=aid,
                source_sheet="Applications",
                source_row=app["source_row"],
            )
        if aid not in proc_apps:
            store.add_finding(
                run_id,
                rule_id="no_process_mapping",
                severity="quality",
                title=f"{aid} supports no recorded business process",
                description="Anti-join: application is not a SupportingApplicationID on BusinessProcesses.",
                entity_type="Application",
                entity_id=aid,
                related_application_id=aid,
                source_sheet="Applications",
                source_row=app["source_row"],
            )


def _sensitive(store, run_id, flows):
    for flow in flows:
        clas = (flow.get("classification") or "").strip()
        if clas.lower() in SENSITIVE_CLASSIFICATIONS:
            store.add_finding(
                run_id,
                rule_id="sensitive_flow",
                severity="sensitive",
                title=f"{clas} flow {flow['flow_id']} ({flow.get('information_object')})",
                description=f"{flow.get('information_object')} moves from {flow.get('source_application_id')} to {flow.get('target_application_id')} classified as {clas}.",
                entity_type="InformationObject",
                entity_id=flow["flow_id"],
                related_application_id=flow.get("source_application_id"),
                source_sheet="InformationObjects",
                source_row=flow["source_row"],
                extra={"classification": clas, "interface_id": flow.get("interface_id")},
            )


def _known_gaps(store, run_id, gaps):
    severity_map = {
        "critical": "blocker",
        "high": "risk",
        "medium": "quality",
        "low": "quality",
        "blocker": "blocker",
        "risk": "risk",
        "quality": "quality",
        "sensitive": "sensitive",
    }
    for gap in gaps:
        sev = severity_map.get((gap.get("severity") or "medium").strip().lower(), "quality")
        store.add_finding(
            run_id,
            rule_id="known_gap",
            severity=sev,
            title=f"Known gap {gap.get('gap_id')}: {gap.get('gap_type')}",
            description=gap.get("description") or "",
            entity_type=gap.get("entity_type") or "KnownDataQualityGap",
            entity_id=gap.get("entity_id"),
            related_application_id=gap.get("related_application_id"),
            source_sheet="KnownDataQualityGaps",
            source_row=gap["source_row"],
            extra={"gap_type": gap.get("gap_type"), "recorded_severity": gap.get("severity")},
        )


def _retired_on_critical_path(store, run_id, apps, rels, procs):
    retired = {
        a["application_id"]
        for a in apps
        if (a.get("lifecycle_status") or "").lower() in {"retired", "decommissioned", "sunset"}
    }
    if not retired:
        return
    crit_rels = [
        r
        for r in rels
        if (r.get("dependency_criticality") or "").lower() in {"high", "mission critical", "mission_critical"}
        and (
            r.get("source_application_id") in retired
            or r.get("target_application_id") in retired
        )
    ]
    for rel in crit_rels:
        rid = rel.get("source_application_id") if rel.get("source_application_id") in retired else rel.get(
            "target_application_id"
        )
        store.add_finding(
            run_id,
            rule_id="retired_on_critical_path",
            severity="risk",
            title=f"Retired application {rid} still on a critical dependency",
            description=f"Relationship {rel.get('relationship_id')} is {rel.get('dependency_criticality')} and includes a retired application.",
            entity_type="Relationship",
            entity_id=rel.get("relationship_id"),
            related_application_id=rid,
            source_sheet="Relationships",
            source_row=rel["source_row"],
        )
    for proc in procs:
        if (proc.get("process_criticality") or "").lower() in {"high", "mission critical", "mission_critical"}:
            aid = proc.get("supporting_application_id")
            if aid in retired:
                store.add_finding(
                    run_id,
                    rule_id="retired_supports_critical_process",
                    severity="risk",
                    title=f"Retired {aid} supports critical process {proc.get('business_process_id')}",
                    description=f"{proc.get('business_process_name')} still lists a retired application as {proc.get('role_of_application')}.",
                    entity_type="BusinessProcess",
                    entity_id=proc.get("process_mapping_id"),
                    related_application_id=aid,
                    source_sheet="BusinessProcesses",
                    source_row=proc["source_row"],
                )
