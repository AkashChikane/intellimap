SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_runs (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  filename TEXT,
  status TEXT,
  note TEXT
);

CREATE TABLE IF NOT EXISTS sheet_reports (
  run_id TEXT NOT NULL,
  sheet TEXT NOT NULL,
  workbook_name TEXT,
  status TEXT,
  row_count INTEGER,
  mapped_headers_json TEXT,
  unmapped_headers_json TEXT,
  missing_fields_json TEXT,
  PRIMARY KEY (run_id, sheet)
);

CREATE TABLE IF NOT EXISTS raw_rows (
  run_id TEXT NOT NULL,
  sheet TEXT NOT NULL,
  row_number INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  original_json TEXT NOT NULL,
  PRIMARY KEY (run_id, sheet, row_number)
);

CREATE TABLE IF NOT EXISTS applications (
  run_id TEXT NOT NULL,
  application_id TEXT NOT NULL,
  application_name TEXT,
  description TEXT,
  business_domain TEXT,
  business_criticality TEXT,
  lifecycle_status TEXT,
  lifecycle_start_date TEXT,
  lifecycle_end_date TEXT,
  hosting TEXT,
  vendor_type TEXT,
  owner_employee_id TEXT,
  cost_center TEXT,
  source_row INTEGER,
  PRIMARY KEY (run_id, application_id)
);

CREATE TABLE IF NOT EXISTS relationships (
  run_id TEXT NOT NULL,
  relationship_id TEXT NOT NULL,
  source_application_id TEXT,
  source_application_name TEXT,
  relationship_type TEXT,
  target_application_id TEXT,
  target_application_name TEXT,
  direction TEXT,
  dependency_criticality TEXT,
  source_row INTEGER,
  PRIMARY KEY (run_id, relationship_id)
);

CREATE TABLE IF NOT EXISTS interfaces (
  run_id TEXT NOT NULL,
  interface_id TEXT NOT NULL,
  interface_name TEXT,
  provider_application_id TEXT,
  provider_application_name TEXT,
  consumer_application_id TEXT,
  consumer_application_name TEXT,
  protocol TEXT,
  data_format TEXT,
  frequency TEXT,
  interface_status TEXT,
  source_row INTEGER,
  PRIMARY KEY (run_id, interface_id)
);

CREATE TABLE IF NOT EXISTS information_objects (
  run_id TEXT NOT NULL,
  flow_id TEXT NOT NULL,
  information_object TEXT,
  classification TEXT,
  source_application_id TEXT,
  source_application_name TEXT,
  target_application_id TEXT,
  target_application_name TEXT,
  operation TEXT,
  interface_id TEXT,
  source_row INTEGER,
  PRIMARY KEY (run_id, flow_id)
);

CREATE TABLE IF NOT EXISTS process_mappings (
  run_id TEXT NOT NULL,
  process_mapping_id TEXT NOT NULL,
  business_process_id TEXT,
  business_process_name TEXT,
  process_domain TEXT,
  supporting_application_id TEXT,
  supporting_application_name TEXT,
  role_of_application TEXT,
  process_criticality TEXT,
  source_row INTEGER,
  PRIMARY KEY (run_id, process_mapping_id)
);

CREATE TABLE IF NOT EXISTS ownership (
  run_id TEXT NOT NULL,
  ownership_id TEXT NOT NULL,
  application_id TEXT,
  application_name TEXT,
  application_owner TEXT,
  owner_employee_id TEXT,
  system_custodian TEXT,
  business_owner TEXT,
  support_group TEXT,
  department TEXT,
  source_row INTEGER,
  PRIMARY KEY (run_id, ownership_id)
);

CREATE TABLE IF NOT EXISTS known_gaps (
  run_id TEXT NOT NULL,
  gap_id TEXT NOT NULL,
  gap_type TEXT,
  entity_type TEXT,
  entity_id TEXT,
  related_application_id TEXT,
  description TEXT,
  severity TEXT,
  source_row INTEGER,
  PRIMARY KEY (run_id, gap_id)
);

CREATE TABLE IF NOT EXISTS findings (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  entity_type TEXT,
  entity_id TEXT,
  related_application_id TEXT,
  source_sheet TEXT,
  source_row INTEGER,
  extra_json TEXT,
  status TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS ai_insights (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  frame_type TEXT,
  frame_id TEXT,
  title TEXT,
  body TEXT,
  related_ids_json TEXT,
  based_on_finding_ids_json TEXT,
  confidence TEXT,
  status TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS review_fixes (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  finding_id TEXT,
  source TEXT NOT NULL,
  status TEXT NOT NULL,
  autofixable INTEGER NOT NULL DEFAULT 0,
  title TEXT,
  rationale TEXT,
  patch_json TEXT,
  created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id);
CREATE INDEX IF NOT EXISTS idx_apps_domain ON applications(run_id, business_domain);
CREATE INDEX IF NOT EXISTS idx_proc_bp ON process_mappings(run_id, business_process_id);
CREATE INDEX IF NOT EXISTS idx_fixes_run ON review_fixes(run_id);
"""
