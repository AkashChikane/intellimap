from __future__ import annotations

import json

from ..ai.provider import complete_json
from ..db.store import Store
from ..ingest.headers import FIELD_ALIASES, normalize_token
from ..ingest.pipeline import TABLE_KEYS
from .fixes import enrich_findings


def _field_name(sheet: str, field: str | None) -> str | None:
    if not field:
        return None
    aliases = FIELD_ALIASES.get(sheet) or {}
    if field in aliases.values():
        return field
    return aliases.get(normalize_token(field))

SYSTEM = """You review an architecture workbook for semantic and data-quality issues.
You receive SOURCE ROWS and DETERMINISTIC FINDINGS. Do not invent ApplicationIDs, relationships, or interfaces that are not in the payload.
Return JSON:
{
  "issues": [
    {
      "finding_id": "existing finding id or null",
      "title": str,
      "description": str,
      "severity": "blocker|risk|quality|sensitive",
      "autofixable": bool,
      "fix_title": str,
      "rationale": str,
      "action": "set_cell|add_row|none",
      "sheet": str,
      "source_row": int or null,
      "field": str or null,
      "after": str or null,
      "payload": {} 
    }
  ]
}
Rules:
- Prefer fixing existing findings over creating new ones.
- set_cell must use an existing sheet + source_row + field from the payload.
- add_row is only allowed for a missing Applications stub using an unresolved ApplicationID already in the findings.
- Max 8 issues. Skip high_centrality, sensitive_flow, and dependency_cycle unless you have a concrete cell edit.
- This is a suggestion, not architecture ground truth.
"""


def scan_review(store: Store, run_id: str) -> list[dict]:
    payload = _payload(store, run_id)
    data = complete_json(SYSTEM, json.dumps(payload)[:14000])
    known_findings = {f["id"]: f for f in store.findings(run_id)}
    known_sheets = set(TABLE_KEYS)
    created = []
    for item in data.get("issues") or []:
        rec = _store_issue(store, run_id, item, known_findings, known_sheets)
        if rec:
            created.append(rec)
    store.commit()
    return created


def _store_issue(store: Store, run_id: str, item: dict, known_findings: dict, known_sheets: set[str]) -> dict | None:
    title = (item.get("title") or item.get("fix_title") or "").strip()
    if not title:
        return None
    finding_id = item.get("finding_id")
    if finding_id not in known_findings:
        finding_id = store.add_finding(
            run_id,
            rule_id="ai_semantic",
            severity=item.get("severity") if item.get("severity") in {"blocker", "risk", "quality", "sensitive"} else "quality",
            title=title,
            description=item.get("description") or item.get("rationale") or "",
            entity_type=item.get("sheet") or "Workbook",
            entity_id="",
            related_application_id=None,
            source_sheet=item.get("sheet") if item.get("sheet") in known_sheets else None,
            source_row=item.get("source_row"),
            extra={"source": "ai"},
        )
    action = (item.get("action") or "none").strip()
    patch = {"action": "none"}
    autofixable = False
    field = _field_name(item.get("sheet") or "", item.get("field"))
    if action == "set_cell" and item.get("sheet") in known_sheets and field and item.get("source_row"):
        raw = store.raw_row(run_id, item["sheet"], int(item["source_row"]))
        if raw and field in (raw.get("payload") or {}):
            patch = {
                "action": "set_cell",
                "sheet": item["sheet"],
                "source_row": int(item["source_row"]),
                "field": field,
                "before": (raw.get("payload") or {}).get(field),
                "after": item.get("after") or "",
            }
            table, key_field = TABLE_KEYS[item["sheet"]]
            patch["key_field"] = key_field
            patch["key_value"] = (raw.get("payload") or {}).get(key_field)
            autofixable = True
    elif action == "add_row" and item.get("sheet") == "Applications":
        payload = item.get("payload") or {}
        aid = (payload.get("application_id") or "").strip()
        unresolved = {
            (f.get("extra") or {}).get("unresolved_id") or f.get("related_application_id")
            for f in known_findings.values()
            if f.get("rule_id") == "unresolved_fk"
        }
        if aid and aid in unresolved and not store.application(run_id, aid):
            patch = {
                "action": "add_row",
                "sheet": "Applications",
                "payload": {
                    "application_id": aid,
                    "application_name": payload.get("application_name") or f"{aid} (added in review)",
                    "description": payload.get("description")
                    or "Placeholder suggested by AI because another sheet referenced this ApplicationID.",
                    "lifecycle_status": payload.get("lifecycle_status") or "Unknown",
                },
            }
            autofixable = True
    if not autofixable and action != "none":
        patch = {"action": "none"}
    return store.add_fix(
        run_id,
        {
            "finding_id": finding_id,
            "source": "ai",
            "status": "proposed",
            "autofixable": autofixable,
            "title": item.get("fix_title") or title,
            "rationale": item.get("rationale") or item.get("description") or "AI suggestion. Not a source fact.",
            "patch": patch,
        },
    )


def _payload(store: Store, run_id: str) -> dict:
    findings = enrich_findings(store, run_id)
    compact_findings = [
        {
            "id": f["id"],
            "rule_id": f.get("rule_id"),
            "severity": f.get("severity"),
            "title": f.get("title"),
            "description": f.get("description"),
            "sheet": f.get("source_sheet"),
            "row": f.get("source_row"),
            "entity_id": f.get("entity_id"),
            "extra": f.get("extra"),
            "status": f.get("status"),
        }
        for f in findings
        if (f.get("status") or "open") == "open"
    ][:80]
    apps = [
        {
            "application_id": a["application_id"],
            "application_name": a.get("application_name"),
            "lifecycle_status": a.get("lifecycle_status"),
            "lifecycle_start_date": a.get("lifecycle_start_date"),
            "lifecycle_end_date": a.get("lifecycle_end_date"),
            "business_domain": a.get("business_domain"),
            "source_row": a.get("source_row"),
        }
        for a in store.applications(run_id)[:80]
    ]
    return {
        "findings": compact_findings,
        "applications": apps,
        "sheets": [s["sheet"] for s in store.sheet_reports(run_id)],
        "note": "IDs are authoritative. Do not invent relationships.",
    }
