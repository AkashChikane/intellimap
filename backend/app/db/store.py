from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schema import SCHEMA


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: str | Path) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    run_cols = {row[1] for row in conn.execute("PRAGMA table_info(ingest_runs)")}
    if "omitted_sheets_json" not in run_cols:
        conn.execute("ALTER TABLE ingest_runs ADD COLUMN omitted_sheets_json TEXT")
    finding_cols = {row[1] for row in conn.execute("PRAGMA table_info(findings)")}
    if "status" not in finding_cols:
        conn.execute("ALTER TABLE findings ADD COLUMN status TEXT DEFAULT 'open'")
    conn.commit()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def rows_to_dicts(rows) -> list[dict]:
    return [row_to_dict(r) for r in rows]


class Store:
    def __init__(self, db_path: str | Path):
        self.conn = connect(db_path)
        self.lock = threading.RLock()

    def _one(self, sql: str, args=()):
        with self.lock:
            return self.conn.execute(sql, args).fetchone()

    def _all(self, sql: str, args=()):
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    def _run(self, sql: str, args=()):
        with self.lock:
            self.conn.execute(sql, args)

    def commit(self):
        with self.lock:
            self.conn.commit()

    def create_run(self, filename: str) -> str:
        run_id = new_id("run")
        self._run(
            "INSERT INTO ingest_runs (id, created_at, filename, status) VALUES (?, ?, ?, ?)",
            (run_id, _now(), filename, "ingesting"),
        )
        self.commit()
        return run_id

    def set_run_status(self, run_id: str, status: str, note: str | None = None):
        self._run(
            "UPDATE ingest_runs SET status = ?, note = ? WHERE id = ?",
            (status, note, run_id),
        )
        self.commit()

    def get_run(self, run_id: str) -> dict | None:
        return row_to_dict(self._one("SELECT * FROM ingest_runs WHERE id = ?", (run_id,)))

    def latest_run(self) -> dict | None:
        return row_to_dict(
            self._one("SELECT * FROM ingest_runs ORDER BY created_at DESC LIMIT 1")
        )

    def add_sheet_report(self, run_id: str, sheet: dict):
        self._run(
            """INSERT INTO sheet_reports
               (run_id, sheet, workbook_name, status, row_count, mapped_headers_json,
                unmapped_headers_json, missing_fields_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                sheet["sheet"],
                sheet.get("workbook_name"),
                sheet["status"],
                sheet["row_count"],
                json.dumps(sheet.get("mapped_headers") or {}),
                json.dumps(sheet.get("unmapped_headers") or []),
                json.dumps(sheet.get("missing_fields") or []),
            ),
        )

    def add_raw_row(self, run_id: str, sheet: str, row_number: int, payload: dict, original: dict):
        self._run(
            "INSERT INTO raw_rows (run_id, sheet, row_number, payload_json, original_json) VALUES (?, ?, ?, ?, ?)",
            (run_id, sheet, row_number, json.dumps(payload), json.dumps(original)),
        )

    def insert_entity(self, table: str, run_id: str, key_field: str, payload: dict, source_row: int) -> bool:
        cols = [c for c in payload.keys()]
        if key_field not in payload or not payload[key_field]:
            return False
        existing = self._one(
            f"SELECT 1 FROM {table} WHERE run_id = ? AND {key_field} = ?",
            (run_id, payload[key_field]),
        )
        if existing:
            return False
        fields = ["run_id", *cols, "source_row"]
        placeholders = ", ".join("?" for _ in fields)
        values = [run_id, *[payload.get(c, "") for c in cols], source_row]
        self._run(
            f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
            values,
        )
        return True

    def add_finding(self, run_id: str, **kwargs) -> str:
        fid = kwargs.get("id") or new_id("fnd")
        self._run(
            """INSERT INTO findings
               (id, run_id, rule_id, severity, title, description, entity_type, entity_id,
                related_application_id, source_sheet, source_row, extra_json, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fid,
                run_id,
                kwargs.get("rule_id"),
                kwargs.get("severity"),
                kwargs.get("title"),
                kwargs.get("description"),
                kwargs.get("entity_type"),
                kwargs.get("entity_id"),
                kwargs.get("related_application_id"),
                kwargs.get("source_sheet"),
                kwargs.get("source_row"),
                json.dumps(kwargs.get("extra") or {}),
                kwargs.get("status") or "open",
            ),
        )
        return fid

    def set_finding_status(self, finding_id: str, status: str):
        self._run("UPDATE findings SET status = ? WHERE id = ?", (status, finding_id))

    def delete_findings(self, run_id: str):
        self._run("DELETE FROM findings WHERE run_id = ?", (run_id,))

    def omitted_sheets(self, run_id: str) -> list[str]:
        run = self.get_run(run_id) or {}
        try:
            return json.loads(run.get("omitted_sheets_json") or "[]")
        except json.JSONDecodeError:
            return []

    def set_omitted_sheets(self, run_id: str, sheets: list[str]):
        self._run(
            "UPDATE ingest_runs SET omitted_sheets_json = ? WHERE id = ?",
            (json.dumps(sheets), run_id),
        )

    def raw_rows(self, run_id: str, sheet: str | None = None, limit: int | None = None) -> list[dict]:
        sql = "SELECT * FROM raw_rows WHERE run_id = ?"
        args: list = [run_id]
        if sheet:
            sql += " AND sheet = ?"
            args.append(sheet)
        sql += " ORDER BY sheet, row_number"
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        rows = rows_to_dicts(self._all(sql, args))
        for r in rows:
            r["payload"] = json.loads(r.pop("payload_json") or "{}")
            r["original"] = json.loads(r.pop("original_json") or "{}")
        return rows

    def raw_row(self, run_id: str, sheet: str, row_number: int) -> dict | None:
        row = row_to_dict(
            self._one(
                "SELECT * FROM raw_rows WHERE run_id = ? AND sheet = ? AND row_number = ?",
                (run_id, sheet, row_number),
            )
        )
        if not row:
            return None
        row["payload"] = json.loads(row.pop("payload_json") or "{}")
        row["original"] = json.loads(row.pop("original_json") or "{}")
        return row

    def upsert_raw_row(self, run_id: str, sheet: str, row_number: int, payload: dict, original: dict):
        self._run(
            """INSERT INTO raw_rows (run_id, sheet, row_number, payload_json, original_json)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(run_id, sheet, row_number) DO UPDATE SET
                 payload_json = excluded.payload_json,
                 original_json = excluded.original_json""",
            (run_id, sheet, row_number, json.dumps(payload), json.dumps(original)),
        )

    def delete_raw_row(self, run_id: str, sheet: str, row_number: int):
        self._run(
            "DELETE FROM raw_rows WHERE run_id = ? AND sheet = ? AND row_number = ?",
            (run_id, sheet, row_number),
        )

    def next_raw_row_number(self, run_id: str, sheet: str) -> int:
        row = self._one(
            "SELECT MAX(row_number) AS n FROM raw_rows WHERE run_id = ? AND sheet = ?",
            (run_id, sheet),
        )
        current = (row["n"] if row and row["n"] is not None else 1)
        return int(current) + 1

    def delete_entities(self, run_id: str, table: str):
        self._run(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))

    def delete_entity(self, table: str, run_id: str, key_field: str, key_val: str):
        self._run(
            f"DELETE FROM {table} WHERE run_id = ? AND {key_field} = ?",
            (run_id, key_val),
        )

    def update_entity_fields(self, table: str, run_id: str, key_field: str, key_val: str, fields: dict):
        if not fields:
            return
        assignments = ", ".join(f"{k} = ?" for k in fields)
        self._run(
            f"UPDATE {table} SET {assignments} WHERE run_id = ? AND {key_field} = ?",
            [*fields.values(), run_id, key_val],
        )

    def add_fix(self, run_id: str, payload: dict) -> dict:
        fid = new_id("fix")
        self._run(
            """INSERT INTO review_fixes
               (id, run_id, finding_id, source, status, autofixable, title, rationale, patch_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fid,
                run_id,
                payload.get("finding_id"),
                payload.get("source") or "deterministic",
                payload.get("status") or "proposed",
                1 if payload.get("autofixable") else 0,
                payload.get("title"),
                payload.get("rationale"),
                json.dumps(payload.get("patch") or {}),
                _now(),
            ),
        )
        return self.get_fix(fid)

    def get_fix(self, fix_id: str) -> dict | None:
        row = row_to_dict(self._one("SELECT * FROM review_fixes WHERE id = ?", (fix_id,)))
        return _fix_view(row) if row else None

    def fixes(self, run_id: str, status: str | None = None) -> list[dict]:
        sql = "SELECT * FROM review_fixes WHERE run_id = ?"
        args: list = [run_id]
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY created_at"
        return [_fix_view(row_to_dict(r)) for r in self._all(sql, args)]

    def set_fix_status(self, fix_id: str, status: str) -> dict | None:
        self._run("UPDATE review_fixes SET status = ? WHERE id = ?", (status, fix_id))
        return self.get_fix(fix_id)

    def clear_unapplied_fixes(self, run_id: str):
        self._run(
            "DELETE FROM review_fixes WHERE run_id = ? AND status IN ('proposed', 'rejected')",
            (run_id,),
        )

    def sheet_reports(self, run_id: str) -> list[dict]:
        rows = rows_to_dicts(
            self._all("SELECT * FROM sheet_reports WHERE run_id = ? ORDER BY sheet", (run_id,))
        )
        for r in rows:
            r["mapped_headers"] = json.loads(r.pop("mapped_headers_json") or "{}")
            r["unmapped_headers"] = json.loads(r.pop("unmapped_headers_json") or "[]")
            r["missing_fields"] = json.loads(r.pop("missing_fields_json") or "[]")
        return rows

    def findings(self, run_id: str) -> list[dict]:
        rows = rows_to_dicts(
            self._all(
                "SELECT * FROM findings WHERE run_id = ? ORDER BY severity, rule_id",
                (run_id,),
            )
        )
        for r in rows:
            r["extra"] = json.loads(r.pop("extra_json") or "{}")
            r["status"] = r.get("status") or "open"
        return rows

    def applications(self, run_id: str) -> list[dict]:
        return rows_to_dicts(
            self._all(
                "SELECT * FROM applications WHERE run_id = ? ORDER BY application_id",
                (run_id,),
            )
        )

    def application(self, run_id: str, application_id: str) -> dict | None:
        return row_to_dict(
            self._one(
                "SELECT * FROM applications WHERE run_id = ? AND application_id = ?",
                (run_id, application_id),
            )
        )

    def relationships(self, run_id: str) -> list[dict]:
        return rows_to_dicts(self._all("SELECT * FROM relationships WHERE run_id = ?", (run_id,)))

    def interfaces(self, run_id: str) -> list[dict]:
        return rows_to_dicts(self._all("SELECT * FROM interfaces WHERE run_id = ?", (run_id,)))

    def flows(self, run_id: str) -> list[dict]:
        return rows_to_dicts(
            self._all("SELECT * FROM information_objects WHERE run_id = ?", (run_id,))
        )

    def processes(self, run_id: str) -> list[dict]:
        return rows_to_dicts(self._all("SELECT * FROM process_mappings WHERE run_id = ?", (run_id,)))

    def ownership(self, run_id: str) -> list[dict]:
        return rows_to_dicts(self._all("SELECT * FROM ownership WHERE run_id = ?", (run_id,)))

    def known_gaps(self, run_id: str) -> list[dict]:
        return rows_to_dicts(self._all("SELECT * FROM known_gaps WHERE run_id = ?", (run_id,)))

    def add_insight(self, run_id: str, payload: dict) -> dict:
        iid = new_id("ins")
        record = {
            "id": iid,
            "run_id": run_id,
            "frame_type": payload.get("frame_type"),
            "frame_id": payload.get("frame_id"),
            "title": payload.get("title"),
            "body": payload.get("body"),
            "related_ids_json": json.dumps(payload.get("related_ids") or []),
            "based_on_finding_ids_json": json.dumps(payload.get("based_on_finding_ids") or []),
            "confidence": payload.get("confidence") or "medium",
            "status": "pending",
            "created_at": _now(),
        }
        self._run(
            """INSERT INTO ai_insights
               (id, run_id, frame_type, frame_id, title, body, related_ids_json,
                based_on_finding_ids_json, confidence, status, created_at)
               VALUES (:id, :run_id, :frame_type, :frame_id, :title, :body, :related_ids_json,
                       :based_on_finding_ids_json, :confidence, :status, :created_at)""",
            record,
        )
        self.commit()
        return self.get_insight(iid)

    def get_insight(self, insight_id: str) -> dict | None:
        row = row_to_dict(self._one("SELECT * FROM ai_insights WHERE id = ?", (insight_id,)))
        return _insight_view(row) if row else None

    def insights(self, run_id: str, frame_type: str | None = None, frame_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM ai_insights WHERE run_id = ?"
        args: list = [run_id]
        if frame_type:
            sql += " AND frame_type = ?"
            args.append(frame_type)
        if frame_id:
            sql += " AND frame_id = ?"
            args.append(frame_id)
        sql += " ORDER BY created_at DESC"
        return [_insight_view(row_to_dict(r)) for r in self._all(sql, args)]

    def set_insight_status(self, insight_id: str, status: str) -> dict | None:
        self._run("UPDATE ai_insights SET status = ? WHERE id = ?", (status, insight_id))
        self.commit()
        return self.get_insight(insight_id)


def _insight_view(row: dict) -> dict:
    row["related_ids"] = json.loads(row.pop("related_ids_json") or "[]")
    row["based_on_finding_ids"] = json.loads(row.pop("based_on_finding_ids_json") or "[]")
    return row


def _fix_view(row: dict) -> dict:
    row["patch"] = json.loads(row.pop("patch_json") or "{}")
    row["autofixable"] = bool(row.get("autofixable"))
    return row
