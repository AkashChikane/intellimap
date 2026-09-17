const SUGGESTIONS = [
  { label: "Focus the seed application", prompt: "Focus the seed application on the diagram." },
  { label: "Where is the bottleneck?", prompt: "Which application is a concentration point or bottleneck in this frame?" },
  { label: "Show unresolved IDs", prompt: "List unresolved application IDs and focus the first one." },
  { label: "Sensitive flows", prompt: "Which information flows are Confidential, PII, or PCI? Highlight the apps involved." },
];

export default function Assistant({
  messages,
  draft,
  setDraft,
  chips,
  setChips,
  dropOn,
  setDropOn,
  onDropNode,
  onSend,
  busy,
  onAction,
  onFocusNode,
}) {
  function onSubmit(e) {
    e.preventDefault();
    if (draft.trim() && !busy) onSend(draft.trim());
  }

  return (
    <div
      className={`assistant ${dropOn ? "drop-on" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDropOn(true);
      }}
      onDragLeave={() => setDropOn(false)}
      onDrop={onDropNode}
    >
      <div className="assistant-head">
        <div>
          <div className="kicker">Assistant</div>
          <p className="muted">Grounded in this frame. Suggestions are not source facts.</p>
        </div>
      </div>

      <div className="assistant-thread">
        {messages.length === 0 && (
          <div className="assistant-empty">
            <p>Ask about ownership, dependencies, or ask me to focus a node on the diagram.</p>
            <div className="assistant-suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s.label} type="button" className="suggest-chip" onClick={() => onSend(s.prompt)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, idx) => (
          <div key={idx} className={`aui-msg ${m.role}`}>
            <div className="aui-role">{m.role === "user" ? "You" : "IntelliMap"}</div>
            <div className="aui-bubble">{m.content}</div>
            {m.role === "assistant" && (m.cards || []).length > 0 && (
              <div className="aui-cards">
                {m.cards.map((card, cidx) => (
                  <div className={`aui-card aui-${card.type}`} key={`${card.id || card.title}-${cidx}`}>
                    <div>
                      <small>{card.type === "node" ? card.kind || "node" : card.severity || "finding"}</small>
                      <b>{card.label || card.title}</b>
                      {card.id && <span className="muted">{card.id}</span>}
                    </div>
                    {card.type === "node" && card.id && (
                      <button type="button" className="btn btn-steel" onClick={() => onFocusNode(card.id)}>
                        Focus
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
            {m.role === "assistant" && (m.actions || []).length > 0 && (
              <div className="aui-actions">
                {m.actions.map((action, aidx) => (
                  <button
                    key={`${action.type}-${aidx}`}
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => onAction(action)}
                  >
                    {action.label || action.type}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="aui-msg assistant"><div className="aui-role">IntelliMap</div><div className="aui-bubble muted">Thinking…</div></div>}
      </div>

      {chips.length > 0 && (
        <div className="chips">
          {chips.map((c) => (
            <span className="chip" key={c.id}>
              {c.label || c.id}
              <button
                type="button"
                className="chip-x"
                aria-label={`Remove ${c.label || c.id}`}
                onClick={() => setChips((list) => list.filter((x) => x.id !== c.id))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <form className="composer aui-composer" onSubmit={onSubmit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask, or drop a node here…"
          disabled={busy}
        />
        <button className="btn btn-primary" type="submit" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
