import { useEffect, useState } from "react";
import { useI18n } from "../i18n";

function hashMatches(id) {
  if (typeof window === "undefined") return false;
  return window.location.hash.replace(/^#/, "") === id;
}

export default function Collapsible({
  id,
  title,
  count,
  defaultOpen = false,
  summary,
  children,
  className = "",
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(() => hashMatches(id) || defaultOpen);

  useEffect(() => {
    function onHash() {
      if (hashMatches(id)) setOpen(true);
    }
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [id]);

  function syncHash(nextOpen) {
    const url = new URL(window.location.href);
    if (nextOpen) {
      url.hash = id;
    } else if (url.hash.replace(/^#/, "") === id) {
      url.hash = "";
    }
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }

  function toggle(event) {
    event.preventDefault();
    setOpen((was) => {
      const next = !was;
      syncHash(next);
      return next;
    });
  }

  return (
    <section className={`collapse ${open ? "is-open" : ""} ${className}`.trim()}>
      <a
        id={id}
        href={`#${id}`}
        className="collapse-toggle"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={`${id}-panel`}
      >
        <span className="collapse-title">
          <span className="chevron" aria-hidden="true">
            ▸
          </span>
          {title}
          {typeof count === "number" && <span className="collapse-count">{count}</span>}
        </span>
        <span className="collapse-action">{open ? t("hide") : t("show")}</span>
      </a>
      {!open && summary ? <div className="collapse-summary">{summary}</div> : null}
      <div id={`${id}-panel`} hidden={!open} className="collapse-panel">
        {children}
      </div>
    </section>
  );
}
