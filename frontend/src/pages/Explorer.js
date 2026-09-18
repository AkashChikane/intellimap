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
import { useBusy } from "../busy";
import { useI18n } from "../i18n";
import { useTheme } from "../theme";

function frameTypes(t) {
  return [
    { id: "application", label: t("frameApplication") },
    { id: "business_process", label: t("frameProcess") },
    { id: "domain", label: t("frameDomain") },
    { id: "information_object", label: t("frameInfo") },
  ];
}

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
  const { t } = useI18n();
  if (!findings.length) {
    return <p className="muted">{t("noFindingsScope")}</p>;
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
  const { t } = useI18n();
  const { run: runBusy } = useBusy();
  const FRAME_TYPES = frameTypes(t);
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
  const [showToolbar, setShowToolbar] = useState(true);
  const [exportBusy, setExportBusy] = useState(false);
  const [excelBusy, setExcelBusy] = useState(false);
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [highlightIds, setHighlightIds] = useState([]);
  const [chatBusy, setChatBusy] = useState(false);
  const [aiReady, setAiReady] = useState(false);
  const [showNodeDetails, setShowNodeDetails] = useState(false);
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
      await runBusy(t("loadingGraph"), async () => {
        const data = await getContext(runId, {
          frame_type: frameType,
          frame_id: frameId,
          hops,
          view,
          hide_unresolved: hideUnresolved,
        });
        setGraph(data);
        setSelected(null);
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }, [runId, frameType, frameId, hops, view, hideUnresolved, runBusy, t]);

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
  }, [showFindings, showInspector, showToolbar, graph]);

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
      await runBusy(t("loadingInsights"), async () => {
        const data = await generateInsights(runId, {
          frame_type: frameType,
          frame_id: frameId,
          hops,
        });
        setGraph((g) => ({ ...g, insights: data.items }));
      });
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
      await runBusy(t("loadingDownload"), () => downloadWorkbook(runId));
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
      await runBusy(t("loadingExport"), () => downloadExport(runId, kind, params, fallback));
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
    showToolbar ? "" : "toolbar-hidden",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={explorerClass}>
      <div className="toolbar">
        {!showToolbar ? (
          <button
            type="button"
            className="btn btn-ghost toolbar-reveal"
            aria-expanded={false}
            onClick={() => setShowToolbar(true)}
          >
            {t("showToolbar")}
          </button>
        ) : (
          <>
        <button
          type="button"
          className={`chip-toggle ${showFindings ? "is-on" : ""}`}
          aria-expanded={showFindings}
          onClick={() => setShowFindings((v) => !v)}
        >
          {showFindings ? t("hideFindings") : t("showFindings")}
          {findings.length ? ` · ${findings.length}` : ""}
        </button>
        <button
          type="button"
          className={`chip-toggle ${showInspector ? "is-on" : ""}`}
          aria-expanded={showInspector}
          onClick={() => setShowInspector((v) => !v)}
        >
          {showInspector ? t("hideAssistant") : t("showAssistant")}
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
          placeholder={t("searchFrame")}
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
          <option value={1}>{t("hop1")}</option>
          <option value={2}>{t("hop2")}</option>
        </select>
        <select className="ctrl" value={view} onChange={(e) => setView(e.target.value)}>
          <option value="deterministic">{t("viewDet")}</option>
          <option value="ai_enhanced">{t("viewEnhanced")}</option>
          <option value="ai_abstract">{t("viewAbstract")}</option>
        </select>
        <button
          type="button"
          className={`chip-toggle ${hideUnresolved ? "is-on" : ""}`}
          onClick={() => setHideUnresolved((v) => !v)}
        >
          {t("hideUnresolved")}
        </button>
        <select className="ctrl" value={theme} onChange={(e) => setTheme(e.target.value)}>
          <option value="navy">{t("svgNavy")}</option>
          <option value="paper">{t("svgPaper")}</option>
          <option value="gray">{t("svgGray")}</option>
        </select>
        <button type="button" className="btn btn-ghost" onClick={() => setSpotlightOpen(true)}>
          {t("find")} {typeof navigator !== "undefined" && /Mac/i.test(navigator.platform || "") ? "⌘K" : "Ctrl+K"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={excelBusy}
          onClick={onDownloadExcel}
        >
          {excelBusy ? t("downloading") : t("downloadExcel")}
        </button>
        <button
          type="button"
          className="btn btn-steel"
          disabled={exportBusy || !frameId}
          onClick={() => onExport("svg")}
        >
          {exportBusy ? t("exporting") : t("exportSvg")}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={exportBusy || !frameId}
          onClick={() => onExport("json")}
        >
          {t("json")}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={exportBusy || !frameId}
          onClick={() => onExport("summary")}
        >
          {t("summary")}
        </button>
        {busy && <span className="muted">{t("loading")}</span>}
        <button
          type="button"
          className="btn btn-ghost"
          aria-expanded={true}
          onClick={() => setShowToolbar(false)}
        >
          {t("hideToolbar")}
        </button>
          </>
        )}
      </div>

      <aside className="side">
        <div className="side-head">
          <span>{t("findings")}</span>
          <button type="button" className="panel-hide" onClick={() => setShowFindings(false)}>
            {t("hide")}
          </button>
        </div>
        <div className="side-body">
          {error && <div className="notice">{error}</div>}
          <div className="frame-card">
            <div className="kicker">{FRAME_TYPES.find((t) => t.id === frameType)?.label}</div>
            <h3>{selectedFrame?.label || frameId || t("chooseFrame")}</h3>
            <p className="muted">
              {t("graphStats", {
                nodes: graph?.stats?.nodes ?? 0,
                edges: graph?.stats?.edges ?? 0,
                unresolved: graph?.stats?.unresolved ?? 0,
              })}
            </p>
            {run && (
              <p className="muted">
                {t("workbookFindings", { file: run.run?.filename, n: run.finding_total })}
              </p>
            )}
          </div>
          <Collapsible
            id="frame-findings"
            title={t("findingsInFrame")}
            count={findings.length}
            summary={
              findings.length
                ? t("findingsHidden", { n: findings.length })
                : t("noFindingsFrame")
            }
          >
            <FindingCards findings={findings} onPick={jumpToFinding} />
          </Collapsible>
          <div className="insight-block">
            <div className="kicker">{t("insightsTitle")}</div>
            <p className="muted">{t("insightsLead")}</p>
            <div className="row">
              <button className="btn btn-steel" disabled={insightBusy} onClick={onInsights}>
                {insightBusy ? t("generating") : t("generateInsights")}
              </button>
            </div>
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
                    {t("accept")}
                  </button>
                  <button className="btn btn-danger" onClick={() => onReview(i.id, "rejected")}>
                    {t("reject")}
                  </button>
                </div>
              </div>
            ))}
          </div>
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
            {t("showFindings")}{findings.length ? ` · ${findings.length}` : ""}
          </button>
        )}
        {!showInspector && (
          <button
            type="button"
            className="panel-tab is-right"
            aria-expanded={false}
            onClick={() => setShowInspector(true)}
          >
            {t("showAssistant")}
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
          <span>{t("assistant")}</span>
          <button type="button" className="panel-hide" onClick={() => setShowInspector(false)}>
            {t("hide")}
          </button>
        </div>
        <div className="rail-body inspector">
          <div className="node-facts">
            <button
              type="button"
              className={`collapse-toggle node-facts-toggle ${showNodeDetails ? "is-open" : ""}`}
              aria-expanded={showNodeDetails}
              onClick={() => setShowNodeDetails((v) => !v)}
            >
              <span className="collapse-title">
                <span className="chevron" aria-hidden="true">
                  ▸
                </span>
                {selected ? selected.data?.label || selected.id : t("nodeDetails")}
              </span>
              <span className="collapse-action">{showNodeDetails ? t("hide") : t("show")}</span>
            </button>
            {showNodeDetails &&
              (selected ? (
                <div className="node-facts-body">
                  <h3>{selected.data?.label || selected.id}</h3>
                  <dl>
                    <dt>ID</dt>
                    <dd>{selected.data?.id || selected.id}</dd>
                    <dt>{t("kind")}</dt>
                    <dd>{selected.data?.kind}</dd>
                    <dt>{t("source")}</dt>
                    <dd>
                      {selected.data?.source_sheet
                        ? `${selected.data.source_sheet} row ${selected.data.source_row}`
                        : t("unresolvedSource")}
                    </dd>
                    <dt>{t("owner")}</dt>
                    <dd>{selected.data?.owner || selected.data?.ownership?.application_owner || "—"}</dd>
                    <dt>{t("lifecycle")}</dt>
                    <dd>{selected.data?.lifecycle || "—"}</dd>
                    <dt>{t("domain")}</dt>
                    <dd>{selected.data?.domain || "—"}</dd>
                  </dl>
                  {selected.data?.ai_note && (
                    <p className="muted" style={{ marginTop: 10 }}>
                      {t("aiNote", { note: selected.data.ai_note })}
                    </p>
                  )}
                  <Collapsible
                    id="inspector-findings"
                    title={t("nodeFindings")}
                    count={nodeFindings.length}
                    summary={
                      nodeFindings.length
                        ? t("nodeFindingsHidden", { n: nodeFindings.length })
                        : t("noFindingsNode")
                    }
                  >
                    <FindingCards findings={nodeFindings} onPick={jumpToFinding} />
                  </Collapsible>
                </div>
              ) : (
                <p className="muted node-facts-body">{t("inspectorFacts")}</p>
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
