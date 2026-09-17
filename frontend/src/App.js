import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useParams } from "react-router-dom";
import ThemeToggle from "./components/ThemeToggle";
import Home from "./pages/Home";
import Explorer from "./pages/Explorer";
import { health } from "./api";

function ExplorerRoute() {
  const { runId } = useParams();
  return <Explorer runId={runId} />;
}

export default function App() {
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
          <span>Architecture context</span>
        </Link>
        <div className="topbar-actions">
          <span
            className={`api-pill ${apiUp === true ? "is-up" : apiUp === false ? "is-down" : ""}`}
          >
            {apiUp === false ? "API offline" : apiUp ? "API ready" : "API…"}
          </span>
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
