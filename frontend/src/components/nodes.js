import { Handle, Position } from "@xyflow/react";

function payload(data) {
  return JSON.stringify({
    id: data.id,
    label: data.label,
    kind: data.kind,
    source_sheet: data.source_sheet,
    source_row: data.source_row,
    domain: data.domain,
    classification: data.classification,
  });
}

function NodeShell({ data, className, children }) {
  const cls = [
    "im-node",
    className,
    data.seed ? "is-seed" : "",
    data.unresolved ? "is-unresolved" : "",
    data.sensitive ? "is-sensitive" : "",
    data.spotlight ? "is-spotlight" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={cls}>
      <Handle type="target" position={Position.Left} />
      {children}
      <div
        className="im-drag"
        draggable
        onDragStart={(e) => {
          e.dataTransfer.setData("application/intellimap-node", payload(data));
          e.dataTransfer.effectAllowed = "copy";
        }}
      >
        Drag into chat
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function ApplicationNode({ data }) {
  return (
    <NodeShell data={data}>
      <div className="im-kicker">{data.id}</div>
      <div className="im-title">{data.label}</div>
      <div className="im-meta">
        {[data.domain, data.lifecycle, data.hosting].filter(Boolean).join(" · ")}
      </div>
      <div className="im-badges">
        {data.unresolved && <span className="badge danger">unresolved</span>}
        {data.sensitive && <span className="badge warn">sensitive</span>}
        {data.boundary && <span className="badge">boundary</span>}
        {(data.risks || []).slice(0, 2).map((r) => (
          <span className="badge" key={r}>
            {r}
          </span>
        ))}
      </div>
    </NodeShell>
  );
}

export function UnresolvedNode({ data }) {
  return (
    <NodeShell data={data} className="is-unresolved">
      <div className="im-kicker">missing in Applications</div>
      <div className="im-title">{data.label}</div>
      <div className="im-meta">Kept as a finding, not discarded.</div>
    </NodeShell>
  );
}

export function ProcessNode({ data }) {
  return (
    <NodeShell data={data} className="is-process">
      <div className="im-kicker">business process</div>
      <div className="im-title">{data.label}</div>
      <div className="im-meta">{data.domain || data.id}</div>
    </NodeShell>
  );
}

export function InformationNode({ data }) {
  return (
    <NodeShell data={data} className="is-info">
      <div className="im-kicker">{data.classification || "information"}</div>
      <div className="im-title">{data.label}</div>
      <div className="im-meta">{data.id}</div>
    </NodeShell>
  );
}

export function GroupNode({ data }) {
  return (
    <div className="im-node is-group">
      <div className="im-kicker">group</div>
      <div className="im-title">{data.label}</div>
      <div className="im-meta">{data.member_count || (data.member_ids || []).length} members</div>
    </div>
  );
}

export const nodeTypes = {
  application: ApplicationNode,
  unresolved: UnresolvedNode,
  process: ProcessNode,
  information: InformationNode,
  groupNode: GroupNode,
};
