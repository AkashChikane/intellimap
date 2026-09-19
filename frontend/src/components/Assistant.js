import { useState } from "react";
import { useI18n } from "../i18n";

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
  onClearNodes,
  onClearChat,
  busy,
  onAction,
  onFocusNode,
}) {
  const { t } = useI18n();
  const [showIntro, setShowIntro] = useState(true);
  const suggestions = [
    { label: t("suggestFocus"), prompt: t("suggestFocusPrompt") },
    { label: t("suggestBottleneck"), prompt: t("suggestBottleneckPrompt") },
    { label: t("suggestUnresolved"), prompt: t("suggestUnresolvedPrompt") },
    { label: t("suggestSensitive"), prompt: t("suggestSensitivePrompt") },
  ];

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
        <div className="kicker">{t("assistantKicker")}</div>
        <div className="assistant-head-actions">
          {(messages.length > 0 || chips.length > 0) && (
            <button type="button" className="panel-hide" onClick={onClearChat} disabled={busy}>
              {t("newChat")}
            </button>
          )}
          <button
            type="button"
            className="panel-hide"
            aria-expanded={showIntro}
            onClick={() => setShowIntro((v) => !v)}
          >
            {showIntro ? t("hide") : t("show")}
          </button>
        </div>
      </div>
      {showIntro && <p className="muted assistant-lead">{t("assistantLead")}</p>}

      <div className="assistant-thread">
        {messages.length === 0 && showIntro && (
          <div className="assistant-empty">
            <p>{t("assistantEmpty")}</p>
            <div className="assistant-suggestions">
              {suggestions.map((s) => (
                <button key={s.label} type="button" className="suggest-chip" onClick={() => onSend(s.prompt)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, idx) => (
          <div key={idx} className={`aui-msg ${m.role}`}>
            <div className="aui-role">{m.role === "user" ? t("you") : "IntelliMap"}</div>
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
                        {t("focus")}
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
        {busy && (
          <div className="aui-msg assistant">
            <div className="aui-role">IntelliMap</div>
            <div className="aui-bubble muted">{t("thinking")}</div>
          </div>
        )}
      </div>

      <div className={`assistant-scope ${chips.length ? "is-pinned" : ""}`}>
        {chips.length > 0 ? (
          <>
            <p className="assistant-scope-label">{t("askingPinned")}</p>
            <div className="chips">
              {chips.map((c) => (
                <span className="chip" key={c.id}>
                  {c.label || c.id}
                  <button
                    type="button"
                    className="chip-x"
                    aria-label={`${t("removeNode")} ${c.label || c.id}`}
                    onClick={() => setChips((list) => list.filter((x) => x.id !== c.id))}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <button type="button" className="btn btn-ghost" onClick={onClearNodes} disabled={busy}>
              {t("wholeDiagram")}
            </button>
          </>
        ) : (
          <p className="assistant-scope-label muted">{t("askingWholeDiagram")}</p>
        )}
      </div>

      <form className="composer aui-composer" onSubmit={onSubmit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={t("askPlaceholder")}
          disabled={busy}
        />
        <button className="btn btn-primary" type="submit" disabled={busy || !draft.trim()}>
          {t("send")}
        </button>
      </form>
    </div>
  );
}
