from __future__ import annotations

from pathlib import Path

from ..db.store import Store
from ..ingest.headers import EXPECTED_SHEETS, SHEET_BLURBS
from ..validate.rules import run_rules
from .excel import parse_workbook

TABLE_KEYS = {
    "Applications": ("applications", "application_id"),
    "Relationships": ("relationships", "relationship_id"),
    "Interfaces": ("interfaces", "interface_id"),
    "InformationObjects": ("information_objects", "flow_id"),
    "BusinessProcesses": ("process_mappings", "process_mapping_id"),
    "ApplicationOwnership": ("ownership", "ownership_id"),
    "KnownDataQualityGaps": ("known_gaps", "gap_id"),
}


def ingest_file(store: Store, path: str | Path) -> dict:
    parsed = parse_workbook(path)
    run_id = store.create_run(parsed["filename"])
    try:
        for sheet in parsed["sheets"]:
            store.add_sheet_report(run_id, sheet)
            table_info = TABLE_KEYS.get(sheet["sheet"])
            seen_keys = set()
            for record in sheet["rows"]:
                payload = record["payload"]
                store.add_raw_row(
                    run_id,
                    sheet["sheet"],
                    record["source_row"],
                    payload,
                    record["original"],
                )
                if not table_info:
                    continue
                table, key = table_info
                key_val = (payload.get(key) or "").strip()
                if not key_val:
                    store.add_finding(
                        run_id,
                        rule_id="missing_key",
                        severity="blocker",
                        title=f"Missing {key} on {sheet['sheet']}",
                        description="Row was stored as source data but not normalized because the primary key is empty.",
                        entity_type=sheet["sheet"],
                        entity_id="",
                        related_application_id=payload.get("application_id")
                        or payload.get("source_application_id")
                        or payload.get("related_application_id"),
                        source_sheet=sheet["sheet"],
                        source_row=record["source_row"],
                    )
                    continue
                if key_val in seen_keys:
                    store.add_finding(
                        run_id,
                        rule_id="duplicate_key",
                        severity="blocker",
                        title=f"Duplicate {key} {key_val}",
                        description="Later duplicate kept in raw_rows only; first occurrence remains the normalized record.",
                        entity_type=sheet["sheet"],
                        entity_id=key_val,
                        related_application_id=payload.get("application_id"),
                        source_sheet=sheet["sheet"],
                        source_row=record["source_row"],
                    )
                    continue
                seen_keys.add(key_val)
                store.insert_entity(table, run_id, key, payload, record["source_row"])
        store.commit()
        run_rules(store, run_id)
        from ..review.fixes import propose_deterministic_fixes

        propose_deterministic_fixes(store, run_id)
        store.set_run_status(run_id, "ready")
    except Exception as exc:
        store.set_run_status(run_id, "failed", str(exc))
        raise
    return summarize(store, run_id)


def rebuild_normalized(store: Store, run_id: str, omitted: list[str] | None = None) -> dict:
    omitted = [s for s in (omitted or []) if s in EXPECTED_SHEETS]
    store.set_omitted_sheets(run_id, omitted)
    for table, _key in TABLE_KEYS.values():
        store.delete_entities(run_id, table)
    store.delete_findings(run_id)
    store.clear_unapplied_fixes(run_id)
    skipped = set(omitted)
    for sheet_name in EXPECTED_SHEETS:
        if sheet_name in skipped:
            continue
        table_info = TABLE_KEYS.get(sheet_name)
        if not table_info:
            continue
        table, key = table_info
        seen_keys = set()
        for record in store.raw_rows(run_id, sheet_name):
            payload = record.get("payload") or {}
            key_val = (payload.get(key) or "").strip()
            source_row = record.get("row_number")
            if not key_val:
                store.add_finding(
                    run_id,
                    rule_id="missing_key",
                    severity="blocker",
                    title=f"Missing {key} on {sheet_name}",
                    description="Row was stored as source data but not normalized because the primary key is empty.",
                    entity_type=sheet_name,
                    entity_id="",
                    related_application_id=payload.get("application_id")
                    or payload.get("source_application_id")
                    or payload.get("related_application_id"),
                    source_sheet=sheet_name,
                    source_row=source_row,
                )
                continue
            if key_val in seen_keys:
                store.add_finding(
                    run_id,
                    rule_id="duplicate_key",
                    severity="blocker",
                    title=f"Duplicate {key} {key_val}",
                    description="Later duplicate kept in raw_rows only; first occurrence remains the normalized record.",
                    entity_type=sheet_name,
                    entity_id=key_val,
                    related_application_id=payload.get("application_id"),
                    source_sheet=sheet_name,
                    source_row=source_row,
                )
                continue
            seen_keys.add(key_val)
            store.insert_entity(table, run_id, key, payload, source_row)
    store.commit()
    run_rules(store, run_id)
    from ..review.fixes import propose_deterministic_fixes

    propose_deterministic_fixes(store, run_id)
    store.set_run_status(run_id, "ready")
    return summarize(store, run_id)


def summarize(store: Store, run_id: str) -> dict:
    run = store.get_run(run_id)
    reports = store.sheet_reports(run_id)
    findings = store.findings(run_id)
    counts = {"blocker": 0, "risk": 0, "quality": 0, "sensitive": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    apps = store.applications(run_id)
    suggested = None
    if apps:
        score = {}
        for f in findings:
            aid = f.get("related_application_id") or ""
            if aid:
                score[aid] = score.get(aid, 0) + 1
        ranked = sorted(
            apps,
            key=lambda a: (
                score.get(a["application_id"], 0),
                1 if (a.get("business_criticality") or "").lower() in {"mission critical", "high"} else 0,
            ),
            reverse=True,
        )
        top = ranked[0]
        suggested = {
            "type": "application",
            "id": top["application_id"],
            "label": top.get("application_name"),
        }
    omitted = set(store.omitted_sheets(run_id))
    open_findings = [f for f in findings if (f.get("status") or "open") == "open"]
    open_counts = {"blocker": 0, "risk": 0, "quality": 0, "sensitive": 0}
    for f in open_findings:
        open_counts[f["severity"]] = open_counts.get(f["severity"], 0) + 1
    sheets = []
    for report in reports:
        item = dict(report)
        item["omitted"] = report["sheet"] in omitted
        item["blurb"] = SHEET_BLURBS.get(report["sheet"], "")
        if item["omitted"]:
            item["include_status"] = "omitted"
        else:
            item["include_status"] = report.get("status")
        sheets.append(item)
    run_view = dict(run or {})
    run_view["omitted_sheets"] = list(omitted)
    return {
        "run": run_view,
        "sheets": sheets,
        "finding_counts": open_counts,
        "finding_total": len(open_findings),
        "finding_total_all": len(findings),
        "suggested_frame": suggested,
        "omitted_sheets": list(omitted),
    }
