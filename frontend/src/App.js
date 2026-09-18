import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useParams } from "react-router-dom";
import LangToggle from "./components/LangToggle";
import ThemeToggle from "./components/ThemeToggle";
import Home from "./pages/Home";
import Explorer from "./pages/Explorer";
import { health } from "./api";
import { useI18n } from "./i18n";

function ExplorerRoute() {
  const { runId } = useParams();
  return <Explorer runId={runId} />;
}

export default function App() {
  const { t } = useI18n();
  const [apiUp, setApiUp] = useState(null);

  useEffect(() => {
    health()
      .then(() => setApiUp(true))
      .catch(() => setApiUp(false));
  }, []);

  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" to="/">
          <span className="brand-mark" aria-hidden="true" />
          <em>IntelliMap</em>
          <span>{t("brandSubtitle")}</span>
        </Link>
        <div className="topbar-actions">
          <span
            data-testid="api-pill"
            className={`api-pill ${apiUp === true ? "is-up" : apiUp === false ? "is-down" : ""}`}
          >
            {apiUp === false ? t("apiOffline") : apiUp ? t("apiReady") : t("apiWait")}
          </span>
          <LangToggle />
          <ThemeToggle />
        </div>
      </header>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/run/:runId" element={<ExplorerRoute />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
