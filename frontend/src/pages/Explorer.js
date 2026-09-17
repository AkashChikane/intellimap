import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  chat,
  downloadExport,
  downloadWorkbook,
  generateInsights,
  getContext,
  getFrames,
  getRun,
  health,
  reviewInsight,
} from "../api";
import Assistant from "../components/Assistant";
import Collapsible from "../components/Collapsible";
import Spotlight from "../components/Spotlight";
import { nodeTypes } from "../components/nodes";
import { useTheme } from "../theme";

const FRAME_TYPES = [
  { id: "application", label: "Application" },
  { id: "business_process", label: "Business process" },
  { id: "domain", label: "Domain" },
  { id: "information_object", label: "Information object" },
];

function styleEdges(edges) {
  return (edges || []).map((e) => {
    const sensitive = e.data?.sensitive;
    const color = sensitive ? "#c45c5c" : e.kind === "supports" ? "#a8a8a8" : "#6091c3";
    let dash;
    if (e.kind === "interface") dash = "6 4";
    if (e.kind === "flow") dash = "2 4";
    if (e.kind === "supports") dash = "1 6";
    return {
      ...e,
      type: "smoothstep",
      animated: e.kind === "flow",
      style: { stroke: color, strokeWidth: 1.6, strokeDasharray: dash },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
    };
  });
}

function findingSource(f) {
  return [
    f.severity,
    f.rule_id,
    f.source_sheet && f.source_row ? `${f.source_sheet} row ${f.source_row}` : f.source_sheet,
    f.entity_id,
  ]
    .filter(Boolean)
    .join(" · ");
}

function findingsForNode(findings, node) {
  if (!node) return [];
  const ids = new Set([node.id, node.data?.id].filter(Boolean));
  return findings.filter((f) => {
    const extra = f.extra || {};
    return (
      ids.has(f.entity_id) ||
      ids.has(f.related_application_id) ||
      ids.has(extra.unresolved_id)
    );
  });
}

function FindingCards({ findings, onPick }) {
  if (!findings.length) {
    return <p className="muted">No findings in this scope.</p>;
  }
  return (
    <div className="filter-list">
      {findings.map((f) => (
        <button
          key={f.id}
          type="button"
          className={`finding-hit sev-${f.severity || "quality"}`}
          onClick={() => onPick?.(f)}
        >
          {f.title}
          <small>{findingSource(f)}</small>
        </button>
      ))}
    </div>
  );
}

export default function Explorer({ runId }) {
  const loc = useLocation();
  const { mode } = useTheme();
  const [run, setRun] = useState(null);
  const [frameType, setFrameType] = useState("application");
  const [frameId, setFrameId] = useState("");
  const [options, setOptions] = useState([]);
  const [query, setQuery] = useState("");
  const [hops, setHops] = useState(1);
  const [view, setView] = useState("deterministic");
  const [hideUnresolved, setHideUnresolved] = useState(false);
  const [graph, setGraph] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [insightBusy, setInsightBusy] = useState(false);
  const [chips, setChips] = useState([]);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [dropOn, setDropOn] = useState(false);
  const [theme, setTheme] = useState("navy");
  const [showFindings, setShowFindings] = useState(false);
  const [showInspector, setShowInspector] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [excelBusy, setExcelBusy] = useState(false);
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [highlightIds, setHighlightIds] = useState([]);
  const [chatBusy, setChatBusy] = useState(false);
  const [aiReady, setAiReady] = useState(false);
  const flowRef = useRef(null);
  const pendingFocusRef = useRef(null);

  useEffect(() => {
    getRun(runId)
      .then((data) => {
        setRun(data);
        const suggested = loc.state?.suggested || data.suggested_frame;
        if (suggested?.id) {
          setFrameType(suggested.type || "application");
          setFrameId(suggested.id);
        }
      })
      .catch((err) => setError(err.message));
  }, [runId, loc.state]);

  useEffect(() => {
    if (!run) return;
    getFrames(runId, frameType, query)
      .then((data) => {
        const items = data.items || [];
        setOptions(items);
        setFrameId((current) => {
          if (current && items.some((i) => i.id === current)) return current;
          const suggested = loc.state?.suggested || run.suggested_frame;
          if (suggested?.type === frameType && items.some((i) => i.id === suggested.id)) {
            return suggested.id;
          }
          return items[0]?.id || "";
        });
      })
      .catch((err) => setError(err.message));
  }, [runId, frameType, query, run, loc.state]);

  const load = useCallback(async () => {
    if (!frameId) return;
    setBusy(true);
    setError("");
    try {
      const data = await getContext(runId, {
        frame_type: frameType,
        frame_id: frameId,
        hops,
        view,
        hide_unresolved: hideUnresolved,
      });
      setGraph(data);
      setSelected(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }, [runId, frameType, frameId, hops, view, hideUnresolved]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    health()
      .then((data) => setAiReady(!!data.llm_ready))
      .catch(() => setAiReady(false));
  }, []);

  useEffect(() => {
    function onKey(e) {
      const key = (e.key || "").toLowerCase();
      if ((e.metaKey || e.ctrlKey) && key === "k") {
        const tag = (e.target && e.target.tagName) || "";
        if (spotlightOpen || !["INPUT", "TEXTAREA", "SELECT"].includes(tag)) {
          e.preventDefault();
          setSpotlightOpen((open) => {
            if (open) {
              setHighlightIds([]);
              pendingFocusRef.current = null;
            }
            return !open;
          });
        }
      } else if (key === "escape") {
        if (spotlightOpen) {
          e.preventDefault();
          setSpotlightOpen(false);
          setHighlightIds([]);
          pendingFocusRef.current = null;
        } else if (highlightIds.length) {
          setHighlightIds([]);
          pendingFocusRef.current = null;
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [spotlightOpen, highlightIds.length]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (pendingFocusRef.current) return;
      flowRef.current?.fitView?.({ padding: 0.16, duration: 200 });
    }, 80);
    return () => clearTimeout(timer);
  }, [showFindings, showInspector, graph]);

  useEffect(() => {
    const id = pendingFocusRef.current;
    if (!id || !graph) return undefined;
    const timer = setTimeout(() => {
      const instance = flowRef.current;
      const n = instance?.getNode?.(id);
      if (!n) return;
      const w = n.measured?.width || 220;
      const h = n.measured?.height || 86;
      instance.setCenter(n.position.x + w / 2, n.position.y + h / 2, { zoom: 1.5, duration: 280 });
    }, 160);
    return () => clearTimeout(timer);
  }, [graph]);

  const rawNodes = graph?.nodes || [];
  const nodes = useMemo(
    () =>
      rawNodes.map((n) => ({
        ...n,
        data: { ...n.data, spotlight: highlightIds.includes(n.id) },
      })),
    [rawNodes, highlightIds]
  );
  const edges = useMemo(() => styleEdges(graph?.edges), [graph]);

  const findings = graph?.findings || [];
  const insights = graph?.insights || [];
  const nodeFindings = useMemo(() => findingsForNode(findings, selected), [findings, selected]);
  const selectedFrame = options.find((o) => o.id === frameId);

  async function onInsights() {
    setInsightBusy(true);
    setError("");
    try {
      const data = await generateInsights(runId, {
        frame_type: frameType,
        frame_id: frameId,
        hops,
      });
      setGraph((g) => ({ ...g, insights: data.items }));
    } catch (err) {
      setError(err.message);
    } finally {
      setInsightBusy(false);
    }
  }

  async function onReview(id, status) {
    const rec = await reviewInsight(runId, id, status);
    setGraph((g) => ({
      ...g,
      insights: (g.insights || []).map((i) => (i.id === id ? rec : i)),
    }));
  }

  function zoomToNode(id) {
    const instance = flowRef.current;
    if (!instance) return;
    const n = instance.getNode(id);
    if (!n) return;
    const w = n.measured?.width || 220;
    const h = n.measured?.height || 86;
    instance.setCenter(n.position.x + w / 2, n.position.y + h / 2, { zoom: 1.5, duration: 280 });
  }

  function focusNode(id) {
    if (!id) return;
    pendingFocusRef.current = id;
    setHighlightIds([id]);
    const node = (graph?.nodes || []).find((n) => n.id === id);
    if (node) setSelected(node);
    setShowInspector(true);
    requestAnimationFrame(() => zoomToNode(id));
    setTimeout(() => zoomToNode(id), 140);
  }

  function closeSpotlight() {
    setSpotlightOpen(false);
    setHighlightIds([]);
    pendingFocusRef.current = null;
  }

  function runAction(action) {
    if (!action) return;
    if (action.type === "focus_node") {
      focusNode(action.node_id);
      return;
    }
    if (action.type === "highlight_nodes") {
      const ids = action.node_ids || [];
      setHighlightIds(ids);
      if (ids[0]) focusNode(ids[0]);
      return;
    }
    if (action.type === "set_hops" && (action.hops === 1 || action.hops === 2)) {
      setHops(action.hops);
      return;
    }
    if (action.type === "set_view" && action.view) {
      setView(action.view);
      return;
    }
    if (action.type === "hide_unresolved") {
      setHideUnresolved(!!action.value);
    }
  }

  async function sendChat(text) {
    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setDraft("");
    setChatBusy(true);
    try {
      const data = await chat(runId, {
        frame_type: frameType,
        frame_id: frameId,
        hops,
        hide_unresolved: hideUnresolved,
        messages: next.map((m) => ({ role: m.role, content: m.content })),
        dropped: chips,
      });
      const reply = {
        role: "assistant",
        content: data.answer || "",
        actions: data.actions || [],
        cards: data.cards || [],
      };
      setMessages([...next, reply]);
      const auto = (data.actions || []).find((a) => a.type === "focus_node" || a.type === "highlight_nodes");
      if (auto) runAction(auto);
    } catch (err) {
      setMessages([...next, { role: "assistant", content: err.message }]);
    } finally {
      setChatBusy(false);
    }
  }

  async function onDownloadExcel() {
    setExcelBusy(true);
    setError("");
    try {
      await downloadWorkbook(runId);
    } catch (err) {
      setError(err.message);
    } finally {
      setExcelBusy(false);
    }
  }

  function onDropNode(e) {
    e.preventDefault();
    setDropOn(false);
    const raw = e.dataTransfer.getData("application/intellimap-node");
    if (!raw) return;
    const node = JSON.parse(raw);
    setChips((c) => (c.some((x) => x.id === node.id) ? c : [...c, node]));
  }

  function jumpToFinding(f) {
    if (f.related_application_id) {
      setFrameType("application");
      setFrameId(f.related_application_id);
    }
  }

  const params = {
    frame_type: frameType,
    frame_id: frameId,
    hops: String(hops),
    view,
    theme,
    hide_unresolved: hideUnresolved ? "true" : "false",
  };

  async function onExport(kind) {
    if (!frameId) {
      setError("Pick a frame before exporting.");
      return;
    }
    setExportBusy(true);
    setError("");
    const ext = kind === "summary" ? "md" : kind;
    const fallback = `intellimap-${frameType}-${frameId}.${ext}`;
    try {
      await downloadExport(runId, kind, params, fallback);
    } catch (err) {
      setError(err.message);
    } finally {
      setExportBusy(false);
    }
  }

  const light = mode === "light";
  const explorerClass = [
    "explorer",
    showFindings ? "" : "findings-hidden",
    showInspector ? "" : "inspector-hidden",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={explorerClass}>
      <div className="toolbar">
        <button
          type="button"
          className={`chip-toggle ${showFindings ? "is-on" : ""}`}
          aria-expanded={showFindings}
          onClick={() => setShowFindings((v) => !v)}
        >
          {showFindings ? "Hide findings" : "Show findings"}
          {findings.length ? ` · ${findings.length}` : ""}
        </button>
        <button
          type="button"
          className={`chip-toggle ${showInspector ? "is-on" : ""}`}
          aria-expanded={showInspector}
          onClick={() => setShowInspector((v) => !v)}
        >
          {showInspector ? "Hide assistant" : "Show assistant"}
        </button>
        <select
          className="ctrl"
          value={frameType}
          onChange={(e) => {
            setFrameType(e.target.value);
            setFrameId("");
          }}
        >
          {FRAME_TYPES.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
        <input
          className="search"
          placeholder="Search this frame type"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select className="ctrl" value={frameId} onChange={(e) => setFrameId(e.target.value)}>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label} ({o.id})
            </option>
          ))}
        </select>
        <select className="ctrl" value={hops} onChange={(e) => setHops(Number(e.target.value))}>
          <option value={1}>1 hop</option>
          <option value={2}>2 hops</option>
        </select>
        <select className="ctrl" value={view} onChange={(e) => setView(e.target.value)}>
          <option value="deterministic">Deterministic</option>
          <option value="ai_enhanced">AI-enhanced</option>
          <option value="ai_abstract">AI abstract</option>
        </select>
        <button
          type="button"
          className={`chip-toggle ${hideUnresolved ? "is-on" : ""}`}
          onClick={() => setHideUnresolved((v) => !v)}
        >
          Hide unresolved
        </button>
        <select className="ctrl" value={theme} onChange={(e) => setTheme(e.target.value)}>
          <option value="navy">SVG navy</option>
          <option value="paper">SVG paper</option>
          <option value="gray">SVG gray</option>
        </select>
        <button type="button" className="btn btn-ghost" onClick={() => setSpotlightOpen(true)}>
          Find {typeof navigator !== "undefined" && /Mac/i.test(navigator.platform || "") ? "⌘K" : "Ctrl+K"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={excelBusy}
          onClick={onDownloadExcel}
        >
          {excelBusy ? "Downloading…" : "Download Excel"}
        </button>
        <button
          type="button"
          className="btn btn-steel"
          disabled={exportBusy || !frameId}
          onClick={() => onExport("svg")}
        >
          {exportBusy ? "Exporting…" : "Export SVG"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={exportBusy || !frameId}
          onClick={() => onExport("json")}
        >
          JSON
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={exportBusy || !frameId}
          onClick={() => onExport("summary")}
        >
          Summary
        </button>
        {busy && <span className="muted">Loading…</span>}
      </div>

      <aside className="side">
        <div className="side-head">
          <span>Findings</span>
          <button type="button" className="panel-hide" onClick={() => setShowFindings(false)}>
            Hide
          </button>
        </div>
        <div className="side-body">
          {error && <div className="notice">{error}</div>}
          <div className="frame-card">
            <div className="kicker">{FRAME_TYPES.find((t) => t.id === frameType)?.label}</div>
            <h3>{selectedFrame?.label || frameId || "Choose a frame"}</h3>
            <p className="muted">
              {graph?.stats?.nodes ?? 0} nodes · {graph?.stats?.edges ?? 0} edges ·{" "}
              {graph?.stats?.unresolved ?? 0} unresolved
            </p>
            {run && (
              <p className="muted">
                {run.run?.filename} · {run.finding_total} workbook findings
              </p>
            )}
          </div>
          <Collapsible
            id="frame-findings"
            title="Findings in frame"
            count={findings.length}
            summary={
              findings.length
                ? `${findings.length} hidden. Show to jump to a related application.`
                : "No findings in this frame."
            }
          >
            <FindingCards findings={findings} onPick={jumpToFinding} />
          </Collapsible>
        </div>
      </aside>

      <div className="canvas">
        {error && !showFindings && <div className="canvas-notice notice">{error}</div>}
        {!showFindings && (
          <button
            type="button"
            className="panel-tab is-left"
            aria-expanded={false}
            onClick={() => setShowFindings(true)}
          >
            Show findings{findings.length ? ` · ${findings.length}` : ""}
          </button>
        )}
        {!showInspector && (
          <button
            type="button"
            className="panel-tab is-right"
            aria-expanded={false}
            onClick={() => setShowInspector(true)}
          >
            Show assistant
          </button>
        )}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.2}
          maxZoom={2}
          colorMode={mode}
          onInit={(instance) => {
            flowRef.current = instance;
            instance.fitView({ padding: 0.16 });
          }}
          onNodeClick={(_, node) => setSelected(node)}
          onPaneClick={() => setSelected(null)}
        >
          <Background color={light ? "#c5d4e6" : "#4d6f99"} gap={22} size={1} />
          <MiniMap
            pannable
            zoomable
            maskColor={light ? "rgba(31,47,87,0.08)" : "rgba(31,47,87,0.55)"}
            nodeColor={() => "#6091c3"}
          />
          <Controls />
        </ReactFlow>
      </div>

      <Spotlight
        open={spotlightOpen}
        onClose={closeSpotlight}
        nodes={rawNodes}
        runId={runId}
        frameType={frameType}
        frameId={frameId}
        hops={hops}
        hideUnresolved={hideUnresolved}
        aiReady={aiReady}
        onPick={(id) => {
          setSpotlightOpen(false);
          focusNode(id);
        }}
      />

      <aside className="rail">
        <div className="rail-head">
          <span>Assistant</span>
          <button type="button" className="panel-hide" onClick={() => setShowInspector(false)}>
            Hide
          </button>
        </div>
        <div className="rail-body inspector">
          {selected ? (
            <>
              <h3>{selected.data?.label || selected.id}</h3>
              <dl>
                <dt>ID</dt>
                <dd>{selected.data?.id || selected.id}</dd>
                <dt>Kind</dt>
                <dd>{selected.data?.kind}</dd>
                <dt>Source</dt>
                <dd>
                  {selected.data?.source_sheet
                    ? `${selected.data.source_sheet} row ${selected.data.source_row}`
                    : "not in Applications (unresolved)"}
                </dd>
                <dt>Owner</dt>
                <dd>{selected.data?.owner || selected.data?.ownership?.application_owner || "—"}</dd>
                <dt>Lifecycle</dt>
                <dd>{selected.data?.lifecycle || "—"}</dd>
                <dt>Domain</dt>
                <dd>{selected.data?.domain || "—"}</dd>
              </dl>
              {selected.data?.ai_note && (
                <p className="muted" style={{ marginTop: 10 }}>
                  AI note: {selected.data.ai_note}
                </p>
              )}
              <Collapsible
                id="inspector-findings"
                title="Findings"
                count={nodeFindings.length}
                summary={
                  nodeFindings.length
                    ? `${nodeFindings.length} hidden for this node.`
                    : "No findings for this node."
                }
              >
                <FindingCards findings={nodeFindings} onPick={jumpToFinding} />
              </Collapsible>
            </>
          ) : (
            <p className="muted">Select a node, press Find, or drop a node onto the assistant.</p>
          )}

          <div className="insight-block">
            <div className="row">
              <button className="btn btn-steel" disabled={insightBusy} onClick={onInsights}>
                {insightBusy ? "Generating…" : "Generate AI insights"}
              </button>
            </div>
            <p className="muted">Generated, not architecture ground truth.</p>
            {(insights || []).map((i) => (
              <div className="finding" key={i.id}>
                <h4>{i.title}</h4>
                <p>{i.body}</p>
                <div className="src">
                  {i.status} · {i.confidence}
                  {i.related_ids?.length ? ` · ${i.related_ids.join(", ")}` : ""}
                </div>
                <div className="row" style={{ marginTop: 8 }}>
                  <button className="btn btn-ok" onClick={() => onReview(i.id, "accepted")}>
                    Accept
                  </button>
                  <button className="btn btn-danger" onClick={() => onReview(i.id, "rejected")}>
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>

          <Assistant
            messages={messages}
            draft={draft}
            setDraft={setDraft}
            chips={chips}
            setChips={setChips}
            dropOn={dropOn}
            setDropOn={setDropOn}
            onDropNode={onDropNode}
            onSend={sendChat}
            busy={chatBusy}
            onAction={runAction}
            onFocusNode={focusNode}
          />
        </div>
      </aside>
    </div>
  );
}
