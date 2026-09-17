from __future__ import annotations

import re

SHEET_ALIASES = {
    "applications": "Applications",
    "relationships": "Relationships",
    "interfaces": "Interfaces",
    "informationobjects": "InformationObjects",
    "informationobject": "InformationObjects",
    "informationflows": "InformationObjects",
    "flows": "InformationObjects",
    "businessprocesses": "BusinessProcesses",
    "businessprocess": "BusinessProcesses",
    "processmappings": "BusinessProcesses",
    "applicationownership": "ApplicationOwnership",
    "ownership": "ApplicationOwnership",
    "knowndataqualitygaps": "KnownDataQualityGaps",
    "dataqualitygaps": "KnownDataQualityGaps",
    "qualitygaps": "KnownDataQualityGaps",
}

FIELD_ALIASES = {
    "Applications": {
        "applicationid": "application_id",
        "applicationname": "application_name",
        "description": "description",
        "businessdomain": "business_domain",
        "businesscriticality": "business_criticality",
        "lifecyclestatus": "lifecycle_status",
        "lifecyclestartdate": "lifecycle_start_date",
        "lifecycleenddate": "lifecycle_end_date",
        "hosting": "hosting",
        "vendortype": "vendor_type",
        "owneremployeeid": "owner_employee_id",
        "costcenter": "cost_center",
    },
    "Relationships": {
        "relationshipid": "relationship_id",
        "sourceapplicationid": "source_application_id",
        "sourceapplicationname": "source_application_name",
        "sourceapplicationilame": "source_application_name",
        "sourceapplicationiane": "source_application_name",
        "relationshiptype": "relationship_type",
        "targetapplicationid": "target_application_id",
        "targetapplicationname": "target_application_name",
        "targetapplicationiane": "target_application_name",
        "direction": "direction",
        "dependencycriticality": "dependency_criticality",
    },
    "Interfaces": {
        "interfaceid": "interface_id",
        "interfacename": "interface_name",
        "interfacellane": "interface_name",
        "providerapplicationid": "provider_application_id",
        "providerapplicationname": "provider_application_name",
        "providerapplicationitame": "provider_application_name",
        "consumerapplicationid": "consumer_application_id",
        "consumerapplicationname": "consumer_application_name",
        "consumerapplicationilame": "consumer_application_name",
        "protocol": "protocol",
        "dataformat": "data_format",
        "frequency": "frequency",
        "interfacestatus": "interface_status",
    },
    "InformationObjects": {
        "flowid": "flow_id",
        "informationobject": "information_object",
        "classification": "classification",
        "sourceapplicationid": "source_application_id",
        "sourceapplicationname": "source_application_name",
        "targetapplicationid": "target_application_id",
        "targetapplicationname": "target_application_name",
        "operation": "operation",
        "interfaceid": "interface_id",
    },
    "BusinessProcesses": {
        "processmappingid": "process_mapping_id",
        "businessprocessid": "business_process_id",
        "businessprocessname": "business_process_name",
        "processdomain": "process_domain",
        "supportingapplicationid": "supporting_application_id",
        "supportingapplicationname": "supporting_application_name",
        "roleofapplication": "role_of_application",
        "processcriticality": "process_criticality",
    },
    "ApplicationOwnership": {
        "ownershipid": "ownership_id",
        "applicationid": "application_id",
        "applicationname": "application_name",
        "applicationowner": "application_owner",
        "owneremployeeid": "owner_employee_id",
        "systemcustodian": "system_custodian",
        "businessowner": "business_owner",
        "supportgroup": "support_group",
        "department": "department",
    },
    "KnownDataQualityGaps": {
        "gapid": "gap_id",
        "gaptype": "gap_type",
        "entitytype": "entity_type",
        "entityid": "entity_id",
        "relatedapplicationid": "related_application_id",
        "description": "description",
        "severity": "severity",
    },
}

EXPECTED_SHEETS = list(FIELD_ALIASES.keys())

SHEET_BLURBS = {
    "Applications": "The application catalog. Every other sheet hangs off ApplicationID.",
    "Relationships": "Directed dependencies between applications.",
    "Interfaces": "Technical connections (provider → consumer).",
    "InformationObjects": "What actually moves across interfaces, including classification.",
    "BusinessProcesses": "Which applications support which business processes.",
    "ApplicationOwnership": "Who owns each application. Can be missing even when the app exists.",
    "KnownDataQualityGaps": "Gaps already recorded in the source landscape.",
}


def pretty_header(field: str) -> str:
    parts = (field or "").split("_")
    out = []
    for part in parts:
        if part in {"id"}:
            out.append("ID")
        else:
            out.append(part[:1].upper() + part[1:] if part else "")
    return "".join(out) or field


def headers_for_sheet(sheet: str) -> list[str]:
    aliases = FIELD_ALIASES.get(sheet) or {}
    seen = []
    for field in aliases.values():
        if field not in seen:
            seen.append(field)
    return [pretty_header(f) for f in seen]


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def canonical_sheet(name: str) -> str | None:
    return SHEET_ALIASES.get(normalize_token(name))


def map_headers(sheet: str, headers: list[str]) -> dict:
    aliases = FIELD_ALIASES[sheet]
    mapped = {}
    unmapped = []
    used = {}
    for raw in headers:
        if raw is None or str(raw).strip() == "":
            continue
        key = normalize_token(str(raw))
        field = aliases.get(key)
        if field:
            mapped[str(raw)] = field
            used[field] = str(raw)
        else:
            unmapped.append(str(raw))
    expected = list(aliases.values())
    missing = [f for f in dict.fromkeys(expected) if f not in used]
    return {
        "mapped": mapped,
        "unmapped": unmapped,
        "missing": missing,
        "used": used,
    }
