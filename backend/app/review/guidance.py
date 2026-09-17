from __future__ import annotations

DEFAULT = {
    "meaning": "A validation check on the workbook. It is not an invented relationship.",
    "how_to_fix": "Open the cited sheet and row, then correct the source data or accept a suggested fix.",
    "autofixable": False,
}

GUIDANCE = {
    "missing_key": {
        "meaning": "This row has no primary ID, so it cannot be part of the landscape graph.",
        "how_to_fix": "Add a unique ID on the cited row, or omit the sheet if the rows are not needed.",
        "autofixable": False,
    },
    "duplicate_key": {
        "meaning": "Two rows share the same ID. Only the first row is used in the graph.",
        "how_to_fix": "Keep one row. Accepting the fix drops the later duplicate from the workbook.",
        "autofixable": True,
    },
    "missing_fk": {
        "meaning": "An application ID field is blank, so the row is incomplete.",
        "how_to_fix": "Fill in the ApplicationID on the cited row. IntelliMap will not guess an ID.",
        "autofixable": False,
    },
    "unresolved_fk": {
        "meaning": "A row points at an ApplicationID that is not in the Applications sheet. The reference is kept as an unresolved node, not deleted.",
        "how_to_fix": "Add the missing application to Applications, or change the ID to an existing one. A placeholder row can be added for you.",
        "autofixable": True,
    },
    "name_mismatch": {
        "meaning": "The name written next to an ApplicationID does not match the Applications catalog. IDs are authoritative; names are labels.",
        "how_to_fix": "Replace the label with the catalog name so the workbook is consistent.",
        "autofixable": True,
    },
    "missing_ownership": {
        "meaning": "The application exists, but ApplicationOwnership has no row for it. Ownership is tracked separately on purpose.",
        "how_to_fix": "Add an ownership row. If Applications already has an OwnerEmployeeID, it can be copied across.",
        "autofixable": True,
    },
    "blank_owner": {
        "meaning": "An ownership row exists but no owner name or employee ID is filled in.",
        "how_to_fix": "Enter an owner, or copy OwnerEmployeeID from the Applications sheet if it is present.",
        "autofixable": True,
    },
    "lifecycle_dates_inverted": {
        "meaning": "LifecycleEndDate is earlier than LifecycleStartDate, so the dates cannot be right.",
        "how_to_fix": "Swap the two dates, or correct whichever one was typed backwards.",
        "autofixable": True,
    },
    "active_past_end": {
        "meaning": "The application is still marked Active (or similar) after its end date.",
        "how_to_fix": "Set LifecycleStatus to Retired, or move the end date forward if it is still live.",
        "autofixable": True,
    },
    "retired_without_end": {
        "meaning": "The application is retired but has no end date, so the timeline is incomplete.",
        "how_to_fix": "Add a LifecycleEndDate. Today’s date can be filled as a placeholder.",
        "autofixable": True,
    },
    "flow_without_interface": {
        "meaning": "An information flow is stored but not linked to an interface.",
        "how_to_fix": "Set InterfaceID to an existing interface, or add the interface first.",
        "autofixable": False,
    },
    "unresolved_interface": {
        "meaning": "A flow points at an InterfaceID that is not in the Interfaces sheet.",
        "how_to_fix": "Add that interface, or point the flow at an interface that exists.",
        "autofixable": False,
    },
    "orphan_interface": {
        "meaning": "The interface exists but no information object uses it. That can be fine.",
        "how_to_fix": "Link a flow to it, or omit the Interfaces row if it is leftover.",
        "autofixable": False,
    },
    "dependency_cycle": {
        "meaning": "Applications depend on each other in a directed loop. That is a risk lens, not a deleted edge.",
        "how_to_fix": "Review the cycle in the explorer and decide which dependency is wrong or should be undirected.",
        "autofixable": False,
    },
    "high_centrality": {
        "meaning": "This application sits on many paths. Concentration is a risk lens, not a defect.",
        "how_to_fix": "No workbook change is required. Use it as a conversation starter in the explorer.",
        "autofixable": False,
    },
    "no_relationships": {
        "meaning": "The application never appears in Relationships. It may be isolated or the sheet is incomplete.",
        "how_to_fix": "Add a relationship if one exists, or leave it — isolation is allowed.",
        "autofixable": False,
    },
    "no_interfaces": {
        "meaning": "The application is neither provider nor consumer on Interfaces.",
        "how_to_fix": "Add an interface row if one exists in the estate.",
        "autofixable": False,
    },
    "no_process_mapping": {
        "meaning": "No business process lists this application as supporting it.",
        "how_to_fix": "Map it on BusinessProcesses if it supports a process; otherwise leave it.",
        "autofixable": False,
    },
    "sensitive_flow": {
        "meaning": "This flow is classified Confidential, PII, or PCI. That is a flag, not an error.",
        "how_to_fix": "No automatic change. Confirm the classification is correct in InformationObjects.",
        "autofixable": False,
    },
    "known_gap": {
        "meaning": "This gap was already recorded on KnownDataQualityGaps. IntelliMap did not invent it.",
        "how_to_fix": "Fix the cited entity in the source sheets, or omit KnownDataQualityGaps if you do not want these listed.",
        "autofixable": False,
    },
    "retired_on_critical_path": {
        "meaning": "A retired application still sits on a high-criticality dependency.",
        "how_to_fix": "Retire the relationship, lower its criticality, or restore the application if it is still required.",
        "autofixable": False,
    },
    "retired_supports_critical_process": {
        "meaning": "A retired application is still listed as supporting a critical business process.",
        "how_to_fix": "Point the process at a live application, or update the process criticality.",
        "autofixable": False,
    },
    "ai_semantic": {
        "meaning": "An AI scan flagged a possible semantic issue. This is a suggestion, not a source fact.",
        "how_to_fix": "Read the rationale. Accept the fix only if it matches the workbook you know.",
        "autofixable": False,
    },
}


def guidance_for(rule_id: str) -> dict:
    item = GUIDANCE.get(rule_id) or DEFAULT
    return {
        "meaning": item["meaning"],
        "how_to_fix": item["how_to_fix"],
        "autofixable": bool(item.get("autofixable")),
    }
