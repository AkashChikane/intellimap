import { useEffect, useMemo, useRef, useState } from "react";
import { searchFrame } from "../api";
import { useI18n } from "../i18n";

function matchNodes(nodes, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return [];
  const tokens = q.split(/\s+/).filter(Boolean);
  const scored = [];
  for (const n of nodes || []) {
    const data = n.data || {};
    const initials = String(data.label || "")
      .split(/\s+/)
      .map((w) => w[0] || "")
      .join("")
      .toLowerCase();
    const hay = [n.id, data.id, data.label, data.kind, data.domain, data.lifecycle, data.owner, data.classification, initials, ...(data.risks || [])]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    if (!tokens.every((t) => hay.includes(t))) continue;
    scored.push({
      id: n.id,
      label: data.label || n.id,
      kind: data.kind,
      reason: "Text match in this frame",
      source: "text",
    });
  }
  return scored.slice(0, 12);
}

export default function Spotlight({
  open,
  onClose,
  nodes,
  runId,
  frameType,
  frameId,
  hops,
  hideUnresolved,
  aiReady,
  onPick,
}) {
  const [mode, setMode] = useState("text");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const { t } = useI18n();

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setResults([]);
    setError("");
    setActive(0);
    const t = setTimeout(() => inputRef.current?.focus(), 20);
    return () => clearTimeout(t);
  }, [open]);

  const local = useMemo(() => matchNodes(nodes, query), [nodes, query]);

  useEffect(() => {
    if (!open) return;
    if (mode !== "text") return;
    setResults(local);
    setActive(0);
  }, [open, mode, local]);

  useEffect(() => {
    if (!open || mode !== "ai") return;
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      return undefined;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      setBusy(true);
      setError("");
      try {
        const data = await searchFrame(runId, {
          query: q,
          frame_type: frameType,
          frame_id: frameId,
          hops,
          hide_unresolved: hideUnresolved,
          mode: "ai",
        });
        if (!cancelled) {
          setResults(data.items || []);
          setActive(0);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
          setResults(local);
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    }, 280);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [open, mode, query, runId, frameType, frameId, hops, hideUnresolved, local]);

  if (!open) return null;

  function pick(item) {
    if (!item) return;
    onPick(item.id);
  }

  function onKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, Math.max(results.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      pick(results[active]);
    }
  }

  return (
    <div className="spotlight-back" onMouseDown={onClose}>
      <div
        className="spotlight"
        role="dialog"
        aria-modal="true"
        aria-label={t("findDialog")}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="spotlight-bar">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder={mode === "ai" ? t("findAiPlaceholder") : t("findPlaceholder")}
          />
          <button type="button" className="spotlight-x" onClick={onClose} aria-label={t("closeFind")}>
            ×
          </button>
        </div>
        <div className="spotlight-modes">
          <button
            type="button"
            className={`chip-toggle ${mode === "text" ? "is-on" : ""}`}
            onClick={() => setMode("text")}
          >
            {t("text")}
          </button>
          <button
            type="button"
            className={`chip-toggle ${mode === "ai" ? "is-on" : ""}`}
            disabled={!aiReady}
            onClick={() => aiReady && setMode("ai")}
            title={aiReady ? t("aiSearchTitle") : t("aiNotConfigured")}
          >
            {t("ai")}
          </button>
          <span className="muted">{busy ? t("searching") : t("findHint")}</span>
        </div>
        {error && <div className="notice spotlight-err">{error}</div>}
        <ul className="spotlight-list">
          {results.map((item, idx) => (
            <li key={item.id}>
              <button
                type="button"
                className={idx === active ? "is-on" : ""}
                onMouseEnter={() => setActive(idx)}
                onClick={() => pick(item)}
              >
                <span>
                  <b>{item.label}</b>
                  <small>
                    {item.kind} · {item.id}
                  </small>
                </span>
                <em>{item.reason}</em>
              </button>
            </li>
          ))}
          {!busy && query.trim() && results.length === 0 && (
            <li className="muted spotlight-empty">{t("noMatches")}</li>
          )}
        </ul>
      </div>
    </div>
  );
}
