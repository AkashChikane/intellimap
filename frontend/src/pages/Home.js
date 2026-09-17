import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  acceptAllFixes,
  downloadWorkbook,
  getReview,
  getSheetPreview,
  ingestFile,
  ingestSample,
  omitSheets,
  reviewFix,
  scanReview,
} from "../api";

const STEPS = [
  { id: "upload", label: "Upload" },
  { id: "sheets", label: "Workbook" },
  { id: "findings", label: "Review" },
];

const SEV_LABEL = {
  blocker: "Breaks the graph",
  risk: "Needs a decision",
  quality: "Hygiene",
  sensitive: "Classification flag",
};

export default function Home() {
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const [findings, setFindings] = useState([]);
  const [filter, setFilter] = useState("");
  const [lane, setLane] = useState("open");
  const [omitted, setOmitted] = useState([]);
  const [activeSheet, setActiveSheet] = useState("Applications");
  const [preview, setPreview] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiNote, setAiNote] = useState("");

  async function onFile(file) {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const data = await ingestFile(file);
      await afterIngest(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function onSample() {
    setBusy(true);
    setError("");
    try {
      const data = await ingestSample();
      await afterIngest(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function afterIngest(data) {
    applyReview(data, data.findings);
    setStep(1);
    setActiveSheet((data.sheets || []).find((s) => s.status !== "missing")?.sheet || "Applications");
    const review = await getReview(data.run.id);
    applyReview(review, review.findings);
  }

  function applyReview(data, items) {
    setSummary(data);
    setFindings(items || data.findings || []);
    setOmitted(data.omitted_sheets || data.run?.omitted_sheets || []);
  }

  useEffect(() => {
    if (step !== 1 || !summary?.run?.id || !activeSheet) return;
    let cancelled = false;
    getSheetPreview(summary.run.id, activeSheet)
      .then((data) => {
        if (!cancelled) setPreview(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [step, summary?.run?.id, activeSheet]);

  async function onContinueFromSheets() {
    setBusy(true);
    setError("");
    try {
      const data = await omitSheets(summary.run.id, omitted);
      const review = await getReview(summary.run.id);
      applyReview({ ...data, ...review }, review.findings);
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function onFix(fixId, status) {
    try {
      const data = await reviewFix(summary.run.id, fixId, status);
      applyReview(data, data.findings);
    } catch (err) {
      setError(err.message);
    }
  }

  async function onAcceptAll() {
    setBusy(true);
    setError("");
    try {
      const data = await acceptAllFixes(summary.run.id);
      applyReview(data, data.findings);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function onScan() {
    setAiBusy(true);
    setError("");
    setAiNote("");
    try {
      const data = await scanReview(summary.run.id);
      applyReview(data, data.findings);
      setAiNote(
        data.disclaimer ||
          `${(data.created || []).length} AI suggestion(s) added. Accept only what matches the workbook.`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setAiBusy(false);
    }
  }

  async function onDownload() {
    setBusy(true);
    setError("");
    try {
      await downloadWorkbook(summary.run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const sheets = summary?.sheets || [];
  const includedCount = sheets.filter((s) => !omitted.includes(s.sheet) && s.status !== "missing").length;
  const openFindings = findings.filter((f) => (f.status || "open") === "open");
  const visible = useMemo(() => {
    const needle = filter.toLowerCase();
    return findings.filter((f) => {
      const isOpen = (f.status || "open") === "open";
      if (lane === "open" && !isOpen) return false;
      if (lane === "resolved" && isOpen) return false;
      if (lane === "autofix" && !(isOpen && (f.fixes || []).some((x) => x.status === "proposed" && x.autofixable))) {
        return false;
      }
      if (lane === "ai" && !(f.fixes || []).some((x) => x.source === "ai")) return false;
      if (lane !== "open" && lane !== "resolved" && lane !== "autofix" && lane !== "ai" && f.severity !== lane) {
        return false;
      }
      if (!needle) return true;
      return (
        (f.title || "").toLowerCase().includes(needle) ||
        (f.entity_id || "").toLowerCase().includes(needle) ||
        (f.rule_id || "").toLowerCase().includes(needle) ||
        (f.meaning || "").toLowerCase().includes(needle)
      );
    });
  }, [findings, filter, lane]);

  return (
    <div className="page">
      <div className="stepper">
        {STEPS.map((s, i) => (
          <button
            key={s.id}
            type="button"
            className={`step ${i === step ? "is-on" : ""} ${i < step ? "is-done" : ""}`}
            onClick={() => {
              if (!summary && i > 0) return;
              if (i === 2 && step === 1) {
                onContinueFromSheets();
                return;
              }
              setStep(i);
            }}
          >
            Step {i + 1}
            <b>{s.label}</b>
          </button>
        ))}
      </div>

      {error && (
        <p className="notice" style={{ maxWidth: 1180, margin: "0 auto 16px" }}>
          {error}
        </p>
      )}

      {step === 0 && (
        <div className="hero">
          <div>
            <div className="kicker">Workbook → review → scoped diagram</div>
            <h1>See the landscape that matters for one decision.</h1>
            <p className="lead">
              Upload the architecture workbook, confirm which sheets belong in this run, then
              review findings with a clear fix for each one. Accepted fixes write back into a
              downloadable Excel file.
            </p>
            <ul className="hero-points">
              <li>Sheets can be omitted before validation is locked in.</li>
              <li>Unresolved keys stay visible — they are never silently dropped.</li>
              <li>AI suggestions appear only in review, and only if you accept them.</li>
            </ul>
          </div>
          <div
            className={`paper drop ${over ? "is-over" : ""} ${busy ? "is-busy" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(false);
              onFile(e.dataTransfer.files[0]);
            }}
          >
            <div className="kicker">Start here</div>
            <h2>Drop an .xlsx landscape</h2>
            <p>Seven expected sheets. ApplicationID is the hub. You can omit any sheet on the next step.</p>
            <div className="row">
              <label className="btn btn-primary">
                Choose workbook
                <input
                  type="file"
                  accept=".xlsx,.xlsm"
                  hidden
                  disabled={busy}
                  onChange={(e) => onFile(e.target.files[0])}
                />
              </label>
              <button className="btn btn-ghost" disabled={busy} onClick={onSample}>
                {busy ? "Ingesting…" : "Load sample landscape"}
              </button>
            </div>
          </div>
        </div>
      )}

      {step === 1 && summary && (
        <WorkbookStep
          summary={summary}
          sheets={sheets}
          omitted={omitted}
          setOmitted={setOmitted}
          activeSheet={activeSheet}
          setActiveSheet={setActiveSheet}
          preview={preview}
          includedCount={includedCount}
          busy={busy}
          onContinue={onContinueFromSheets}
        />
      )}

      {step === 2 && summary && (
        <ReviewStep
          summary={summary}
          findings={visible}
          openCount={openFindings.length}
          filter={filter}
          setFilter={setFilter}
          lane={lane}
          setLane={setLane}
          aiBusy={aiBusy}
          aiNote={aiNote}
          busy={busy}
          onFix={onFix}
          onAcceptAll={onAcceptAll}
          onScan={onScan}
          onDownload={onDownload}
          onExplore={() =>
            nav(`/run/${summary.run.id}`, {
              state: { suggested: summary.suggested_frame },
            })
          }
        />
      )}
    </div>
  );
}

function WorkbookStep({
  summary,
  sheets,
  omitted,
  setOmitted,
  activeSheet,
  setActiveSheet,
  preview,
  includedCount,
  busy,
  onContinue,
}) {
  const current = sheets.find((s) => s.sheet === activeSheet) || sheets[0];
  const isOmitted = omitted.includes(activeSheet);
  const headers = preview?.headers || [];

  function toggleOmit(sheet, next) {
    setOmitted((list) => {
      if (next) return list.includes(sheet) ? list : [...list, sheet];
      return list.filter((s) => s !== sheet);
    });
  }

  return (
    <div className="stage workbook-stage">
      <div className="workbook-intro">
        <div>
          <div className="kicker">Workbook</div>
          <h2>{summary.run.filename}</h2>
          <p className="muted">
            This is the file as ingested. Include a sheet to use it in the landscape, or omit it
            so it is skipped in validation, the graph, and the downloaded workbook.
          </p>
        </div>
        <div className="workbook-meta">
          {includedCount} of {sheets.length} sheets included
        </div>
      </div>

      <div className="workbook">
        <div className="sheet-tabs" role="tablist">
          {sheets.map((s) => {
            const skipped = omitted.includes(s.sheet) || s.status === "missing";
            return (
              <button
                key={s.sheet}
                type="button"
                role="tab"
                aria-selected={s.sheet === activeSheet}
                className={`sheet-tab ${s.sheet === activeSheet ? "is-on" : ""} ${
                  skipped ? "is-omitted" : ""
                }`}
                onClick={() => setActiveSheet(s.sheet)}
              >
                {s.sheet}
                <small>{skipped ? "omitted" : `${s.row_count} rows`}</small>
              </button>
            );
          })}
        </div>

        {current && (
          <div className="sheet-stage">
            <div className="sheet-toolbar">
              <div>
                <h3>{current.sheet}</h3>
                <p className="muted">{current.blurb}</p>
              </div>
              <label className={`include-toggle ${isOmitted ? "is-off" : ""}`}>
                <input
                  type="checkbox"
                  checked={!isOmitted && current.status !== "missing"}
                  disabled={current.status === "missing"}
                  onChange={(e) => toggleOmit(current.sheet, !e.target.checked)}
                />
                {current.status === "missing"
                  ? "Not in file"
                  : isOmitted
                    ? "Omitted from this run"
                    : "Include in this run"}
              </label>
            </div>
            <div className="sheet-stats">
              <span className={`status ${current.status}`}>{current.status}</span>
              {current.workbook_name && <span>File tab “{current.workbook_name}”</span>}
              <span>{current.row_count} data rows</span>
              {current.missing_fields?.length > 0 && (
                <span>Unmapped: {current.missing_fields.join(", ")}</span>
              )}
              {current.unmapped_headers?.length > 0 && (
                <span>Ignored headers: {current.unmapped_headers.join(", ")}</span>
              )}
            </div>
            {current.status === "missing" ? (
              <p className="muted empty-sheet">This expected sheet was not in the workbook.</p>
            ) : (
              <div className="sheet-scroll">
                <table className="sheet-table">
                  <thead>
                    <tr>
                      <th className="row-num">#</th>
                      {headers.map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(preview?.rows || []).map((row) => (
                      <tr key={row.source_row}>
                        <td className="row-num">{row.source_row}</td>
                        {headers.map((h) => (
                          <td key={h}>{row.values?.[h] || ""}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {preview?.truncated && (
                  <p className="muted sheet-more">Showing the first {preview.rows.length} rows.</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="row workbook-actions">
        <button className="btn btn-steel" disabled={busy || includedCount === 0} onClick={onContinue}>
          {busy ? "Updating…" : `Review findings · ${includedCount} sheets`}
        </button>
        {omitted.includes("Applications") && (
          <span className="muted">Omitting Applications will leave the graph without a hub.</span>
        )}
      </div>
    </div>
  );
}

function ReviewStep({
  summary,
  findings,
  openCount,
  filter,
  setFilter,
  lane,
  setLane,
  aiBusy,
  aiNote,
  busy,
  onFix,
  onAcceptAll,
  onScan,
  onDownload,
  onExplore,
}) {
  const counts = summary.finding_counts || {};
  return (
    <div className="stage review-stage">
      <div className="review-intro">
        <div>
          <div className="kicker">Review</div>
          <h2>What these findings are</h2>
          <p>
            Each card is a check on the workbook you just confirmed. It is not a new
            relationship. Blockers break IDs in the graph. Risks need a human decision. Quality
            is hygiene. Sensitive means Confidential, PII, or PCI — a flag, not a defect.
          </p>
        </div>
        <div className="review-counts">
          <b>{openCount}</b>
          <span>open</span>
        </div>
      </div>

      <div className="toolbar findings-bar">
        <input
          className="search"
          placeholder="Search title, ID, or meaning"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <div className="lane-pills">
          {[
            ["open", `Open · ${openCount}`],
            ["autofix", "Autofixable"],
            ["ai", "AI"],
            ["blocker", `Blockers · ${counts.blocker || 0}`],
            ["risk", `Risks · ${counts.risk || 0}`],
            ["quality", `Quality · ${counts.quality || 0}`],
            ["sensitive", `Sensitive · ${counts.sensitive || 0}`],
            ["resolved", "Resolved"],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`chip-toggle ${lane === id ? "is-on" : ""}`}
              onClick={() => setLane(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="row review-actions">
        <button className="btn btn-ghost" disabled={aiBusy || busy} onClick={onScan}>
          {aiBusy ? "Scanning…" : "Scan with AI"}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={onAcceptAll}>
          Accept all autofixes
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={onDownload}>
          Download fixed Excel
        </button>
        <button className="btn btn-steel" onClick={onExplore}>
          Open context explorer
        </button>
      </div>
      {aiNote && <p className="ok-note">{aiNote}</p>}

      <div className="finding-list">
        {findings.length === 0 && <p className="muted">Nothing in this filter.</p>}
        {findings.map((f) => (
          <FindingCard key={f.id} finding={f} onFix={onFix} />
        ))}
      </div>
    </div>
  );
}

function FindingCard({ finding, onFix }) {
  const proposed = (finding.fixes || []).filter((fx) => fx.status === "proposed");
  const applied = (finding.fixes || []).some((fx) => fx.status === "applied" || fx.status === "accepted");
  return (
    <article className={`finding-card sev-${finding.severity} ${finding.status === "resolved" ? "is-resolved" : ""}`}>
      <header>
        <span className={`sev-pill sev-${finding.severity}`}>{finding.severity}</span>
        <span className="muted">{SEV_LABEL[finding.severity]}</span>
        {finding.autofixable && <span className="tag">Autofixable</span>}
        {proposed.some((fx) => fx.source === "ai") && <span className="tag tag-ai">AI</span>}
        {finding.status === "resolved" && <span className="tag tag-ok">Resolved</span>}
      </header>
      <h3>{finding.title}</h3>
      <p className="finding-desc">{finding.description}</p>
      <dl className="finding-guide">
        <div>
          <dt>What this means</dt>
          <dd>{finding.meaning}</dd>
        </div>
        <div>
          <dt>How to fix</dt>
          <dd>{finding.how_to_fix}</dd>
        </div>
      </dl>
      <div className="src">
        {finding.rule_id}
        {finding.source_sheet ? ` · ${finding.source_sheet}` : ""}
        {finding.source_row ? ` row ${finding.source_row}` : ""}
        {finding.entity_id ? ` · ${finding.entity_id}` : ""}
      </div>
      {proposed.map((fx) => (
        <div className={`fix-box ${fx.source === "ai" ? "is-ai" : ""}`} key={fx.id}>
          <div className="fix-head">
            <strong>{fx.source === "ai" ? "AI suggestion" : "Suggested fix"}</strong>
            <span>{fx.title}</span>
          </div>
          <p>{fx.rationale}</p>
          <PatchPreview patch={fx.patch} />
          <div className="row">
            {fx.autofixable && fx.patch?.action !== "none" ? (
              <button className="btn btn-ok" onClick={() => onFix(fx.id, "accepted")}>
                Accept fix
              </button>
            ) : (
              <span className="muted">No automatic edit — use this as guidance.</span>
            )}
            <button className="btn btn-danger" onClick={() => onFix(fx.id, "rejected")}>
              Reject
            </button>
          </div>
        </div>
      ))}
      {applied && proposed.length === 0 && (
        <p className="muted">This fix was applied to the working workbook.</p>
      )}
    </article>
  );
}

function PatchPreview({ patch }) {
  if (!patch || patch.action === "none") return null;
  if (patch.action === "add_row") {
    return (
      <p className="patch">
        Add a row on <b>{patch.sheet}</b>
        {patch.payload?.application_id ? ` for ${patch.payload.application_id}` : ""}.
      </p>
    );
  }
  if (patch.action === "drop_row") {
    return (
      <p className="patch">
        Remove {patch.sheet} row {patch.source_row}.
      </p>
    );
  }
  const cells = patch.cells || (patch.field ? [{ field: patch.field, before: patch.before, after: patch.after }] : []);
  if (!cells.length) return null;
  return (
    <ul className="patch-list">
      {cells.map((c) => (
        <li key={c.field}>
          <code>{c.field}</code>
          <span className="before">{c.before || "blank"}</span>
          <span aria-hidden="true">→</span>
          <span className="after">{c.after || "blank"}</span>
        </li>
      ))}
    </ul>
  );
}
