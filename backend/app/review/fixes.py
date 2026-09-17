from __future__ import annotations

from datetime import datetime, timezone

from ..db.store import Store
from ..ingest.headers import FIELD_ALIASES, pretty_header
from ..ingest.pipeline import TABLE_KEYS
from .guidance import guidance_for


def propose_deterministic_fixes(store: Store, run_id: str) -> list[dict]:
    existing = {
        (fx.get("finding_id"), fx.get("source"))
        for fx in store.fixes(run_id)
        if fx.get("status") in {"proposed", "accepted", "applied"}
    }
    created = []
    stubbed = set()
    for finding in store.findings(run_id):
        if (finding.get("status") or "open") != "open":
            continue
        patch = _deterministic_patch(store, run_id, finding, stubbed)
        if not patch:
            continue
        key = (finding["id"], "deterministic")
        if key in existing:
            continue
        rec = store.add_fix(
            run_id,
            {
                "finding_id": finding["id"],
                "source": "deterministic",
                "status": "proposed",
                "autofixable": True,
                "title": patch["title"],
                "rationale": patch["rationale"],
                "patch": patch["patch"],
            },
        )
        created.append(rec)
    store.commit()
    return created


def enrich_findings(store: Store, run_id: str) -> list[dict]:
    by_finding: dict[str, list] = {}
    for fx in store.fixes(run_id):
        by_finding.setdefault(fx.get("finding_id") or "", []).append(fx)
    items = []
    for finding in store.findings(run_id):
        guide = guidance_for(finding.get("rule_id") or "")
        item = dict(finding)
        item["status"] = item.get("status") or "open"
        item["meaning"] = guide["meaning"]
        item["how_to_fix"] = guide["how_to_fix"]
        item["autofixable"] = guide["autofixable"]
        item["fixes"] = by_finding.get(finding["id"], [])
        items.append(item)
    order = {"blocker": 0, "risk": 1, "sensitive": 2, "quality": 3}
    items.sort(key=lambda f: (0 if f.get("status") == "open" else 1, order.get(f.get("severity"), 9), f.get("rule_id") or ""))
    return items


def apply_fix(store: Store, run_id: str, fix_id: str, status: str) -> dict:
    rec = store.get_fix(fix_id)
    if not rec or rec.get("run_id") != run_id:
        raise KeyError("Unknown fix")
    if status == "rejected":
        store.set_fix_status(fix_id, "rejected")
        store.commit()
        return store.get_fix(fix_id)
    if status != "accepted":
        raise ValueError("status must be accepted or rejected")
    if rec.get("status") in {"accepted", "applied"}:
        return rec
    _apply_patch(store, run_id, rec.get("patch") or {})
    store.set_fix_status(fix_id, "applied")
    finding_id = rec.get("finding_id")
    if finding_id:
        store.set_finding_status(finding_id, "resolved")
        _resolve_related(store, run_id, rec)
    store.commit()
    return store.get_fix(fix_id)


def accept_all_autofixes(store: Store, run_id: str) -> dict:
    applied = 0
    for fx in store.fixes(run_id, status="proposed"):
        if not fx.get("autofixable"):
            continue
        apply_fix(store, run_id, fx["id"], "accepted")
        applied += 1
    return {"applied": applied}


def _deterministic_patch(store: Store, run_id: str, finding: dict, stubbed: set[str]) -> dict | None:
    rule = finding.get("rule_id")
    extra = finding.get("extra") or {}
    sheet = finding.get("source_sheet")
    row = finding.get("source_row")
    if rule == "name_mismatch":
        return _name_mismatch_patch(store, run_id, finding)
    if rule == "lifecycle_dates_inverted":
        app = store.application(run_id, finding.get("entity_id"))
        if not app:
            return None
        return {
            "title": f"Swap lifecycle dates for {app['application_id']}",
            "rationale": "End date is before start date. Swapping them restores a valid range.",
            "patch": {
                "action": "set_cells",
                "sheet": "Applications",
                "source_row": app.get("source_row"),
                "key_field": "application_id",
                "key_value": app["application_id"],
                "cells": [
                    {
                        "field": "lifecycle_start_date",
                        "before": app.get("lifecycle_start_date"),
                        "after": app.get("lifecycle_end_date"),
                    },
                    {
                        "field": "lifecycle_end_date",
                        "before": app.get("lifecycle_end_date"),
                        "after": app.get("lifecycle_start_date"),
                    },
                ],
            },
        }
    if rule == "active_past_end":
        return _set_app_field(
            store,
            run_id,
            finding.get("entity_id"),
            "lifecycle_status",
            "Retired",
            title=f"Mark {finding.get('entity_id')} as Retired",
            rationale="Status is still Active after the recorded end date.",
        )
    if rule == "retired_without_end":
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return _set_app_field(
            store,
            run_id,
            finding.get("entity_id"),
            "lifecycle_end_date",
            today,
            title=f"Set end date for {finding.get('entity_id')}",
            rationale="Retired applications should carry a LifecycleEndDate. Today is used as a placeholder.",
        )
    if rule == "unresolved_fk":
        aid = extra.get("unresolved_id") or finding.get("related_application_id")
        if not aid or aid in stubbed or store.application(run_id, aid):
            return None
        stubbed.add(aid)
        return {
            "title": f"Add placeholder application {aid}",
            "rationale": "A row references this ID, but Applications has no matching row. A stub keeps the ID visible instead of dropping the reference.",
            "patch": {
                "action": "add_row",
                "sheet": "Applications",
                "payload": {
                    "application_id": aid,
                    "application_name": f"{aid} (added in review)",
                    "description": "Placeholder added because another sheet referenced this ApplicationID.",
                    "lifecycle_status": "Unknown",
                },
            },
        }
    if rule == "missing_ownership":
        aid = finding.get("entity_id")
        app = store.application(run_id, aid) if aid else None
        if not app:
            return None
        owner = (app.get("owner_employee_id") or "").strip()
        return {
            "title": f"Add ownership row for {aid}",
            "rationale": "Applications has this ID but ApplicationOwnership does not. OwnerEmployeeID is copied when present.",
            "patch": {
                "action": "add_row",
                "sheet": "ApplicationOwnership",
                "payload": {
                    "ownership_id": f"OWN-{aid}",
                    "application_id": aid,
                    "application_name": app.get("application_name") or "",
                    "owner_employee_id": owner,
                    "application_owner": owner,
                },
            },
        }
    if rule == "blank_owner":
        own_row = store.raw_row(run_id, "ApplicationOwnership", row) if row else None
        aid = finding.get("related_application_id")
        app = store.application(run_id, aid) if aid else None
        owner = ((app or {}).get("owner_employee_id") or "").strip()
        if not own_row or not owner:
            return None
        return {
            "title": f"Copy owner {owner} onto ownership row",
            "rationale": "Applications already has OwnerEmployeeID; the ownership row is blank.",
            "patch": {
                "action": "set_cells",
                "sheet": "ApplicationOwnership",
                "source_row": row,
                "key_field": "ownership_id",
                "key_value": (own_row["payload"] or {}).get("ownership_id"),
                "cells": [
                    {"field": "owner_employee_id", "before": "", "after": owner},
                    {"field": "application_owner", "before": "", "after": owner},
                ],
            },
        }
    if rule == "duplicate_key" and sheet and row:
        return {
            "title": f"Drop duplicate row {row} on {sheet}",
            "rationale": "The first occurrence of this ID is already the normalized record. The later duplicate is removed from the workbook.",
            "patch": {"action": "drop_row", "sheet": sheet, "source_row": row},
        }
    return None


def _set_app_field(store, run_id, app_id, field, after, title, rationale):
    app = store.application(run_id, app_id)
    if not app:
        return None
    before = app.get(field) or ""
    if before == after:
        return None
    return {
        "title": title,
        "rationale": rationale,
        "patch": {
            "action": "set_cells",
            "sheet": "Applications",
            "source_row": app.get("source_row"),
            "key_field": "application_id",
            "key_value": app_id,
            "cells": [{"field": field, "before": before, "after": after}],
        },
    }


def _name_mismatch_patch(store: Store, run_id: str, finding: dict) -> dict | None:
    extra = finding.get("extra") or {}
    recorded = extra.get("recorded_name")
    canonical = extra.get("canonical_name")
    sheet = finding.get("source_sheet")
    row = finding.get("source_row")
    if not sheet or not row or not canonical:
        return None
    raw = store.raw_row(run_id, sheet, row)
    if not raw:
        return None
    payload = raw.get("payload") or {}
    field = None
    for key, val in payload.items():
        if key.endswith("_name") and val == recorded:
            field = key
            break
    if not field:
        return None
    table, key_field = TABLE_KEYS.get(sheet, (None, None))
    return {
        "title": f"Use catalog name “{canonical}”",
        "rationale": "ApplicationID is authoritative. The label on this row is rewritten to match Applications.",
        "patch": {
            "action": "set_cells",
            "sheet": sheet,
            "source_row": row,
            "key_field": key_field,
            "key_value": payload.get(key_field) if key_field else finding.get("entity_id"),
            "cells": [{"field": field, "before": recorded, "after": canonical}],
        },
    }


def _apply_patch(store: Store, run_id: str, patch: dict) -> None:
    action = patch.get("action")
    sheet = patch.get("sheet")
    if action == "set_cells":
        cells = patch.get("cells") or []
        if patch.get("field"):
            cells = [{"field": patch["field"], "before": patch.get("before"), "after": patch.get("after")}]
        _set_cells(
            store,
            run_id,
            sheet,
            patch.get("source_row"),
            patch.get("key_field"),
            patch.get("key_value"),
            cells,
        )
    elif action == "set_cell":
        _set_cells(
            store,
            run_id,
            sheet,
            patch.get("source_row"),
            patch.get("key_field"),
            patch.get("key_value"),
            [{"field": patch.get("field"), "before": patch.get("before"), "after": patch.get("after")}],
        )
    elif action == "add_row":
        _add_row(store, run_id, sheet, patch.get("payload") or {})
    elif action == "drop_row":
        _drop_row(store, run_id, sheet, patch.get("source_row"))
    else:
        raise ValueError(f"Unsupported patch action {action}")


def _set_cells(store, run_id, sheet, source_row, key_field, key_value, cells):
    allowed = set((FIELD_ALIASES.get(sheet) or {}).values())
    fields = {
        c["field"]: c.get("after") if c.get("after") is not None else ""
        for c in cells
        if c.get("field") in allowed
    }
    if not fields:
        return
    if source_row:
        raw = store.raw_row(run_id, sheet, source_row)
        if raw:
            payload = dict(raw.get("payload") or {})
            original = dict(raw.get("original") or {})
            payload.update(fields)
            for field, value in fields.items():
                original[pretty_header(field)] = value
                for header in list(original):
                    if header.replace(" ", "").lower() == field.replace("_", "").lower():
                        original[header] = value
            store.upsert_raw_row(run_id, sheet, source_row, payload, original)
    table_info = TABLE_KEYS.get(sheet)
    if table_info and key_field and key_value:
        table, _ = table_info
        store.update_entity_fields(table, run_id, key_field, key_value, fields)


def _add_row(store, run_id, sheet, payload: dict):
    table_info = TABLE_KEYS.get(sheet)
    if not table_info:
        raise ValueError(f"Unknown sheet {sheet}")
    table, key_field = table_info
    row_number = store.next_raw_row_number(run_id, sheet)
    original = {pretty_header(k): v for k, v in payload.items()}
    store.upsert_raw_row(run_id, sheet, row_number, payload, original)
    store.insert_entity(table, run_id, key_field, payload, row_number)


def _drop_row(store, run_id, sheet, source_row):
    raw = store.raw_row(run_id, sheet, source_row) if source_row else None
    if raw:
        payload = raw.get("payload") or {}
        table_info = TABLE_KEYS.get(sheet)
        if table_info:
            table, key_field = table_info
            key_val = payload.get(key_field)
            if key_val:
                store.delete_entity(table, run_id, key_field, key_val)
        store.delete_raw_row(run_id, sheet, source_row)


def _resolve_related(store: Store, run_id: str, rec: dict):
    patch = rec.get("patch") or {}
    if patch.get("action") == "add_row" and patch.get("sheet") == "Applications":
        aid = (patch.get("payload") or {}).get("application_id")
        if not aid:
            return
        for finding in store.findings(run_id):
            extra = finding.get("extra") or {}
            if finding.get("rule_id") == "unresolved_fk" and (
                extra.get("unresolved_id") == aid or finding.get("related_application_id") == aid
            ):
                store.set_finding_status(finding["id"], "resolved")
                for fx in store.fixes(run_id):
                    if fx.get("finding_id") == finding["id"] and fx.get("status") == "proposed":
                        store.set_fix_status(fx["id"], "applied")
