import { createContext, useCallback, useContext, useMemo, useState } from "react";

const MIN_MS = 800;
const BusyContext = createContext({
  label: "",
  run: async (_label, fn) => fn(),
});

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function withMinDelay(work, ms = MIN_MS) {
  const started = Date.now();
  try {
    const result = await work;
    const remaining = ms - (Date.now() - started);
    if (remaining > 0) await wait(remaining);
    return result;
  } catch (err) {
    const remaining = Math.min(400, ms - (Date.now() - started));
    if (remaining > 0) await wait(remaining);
    throw err;
  }
}

export function BusyProvider({ children }) {
  const [label, setLabel] = useState("");

  const run = useCallback(async (text, fn) => {
    setLabel(text);
    try {
      return await withMinDelay(Promise.resolve().then(fn));
    } finally {
      setLabel("");
    }
  }, []);

  const value = useMemo(() => ({ label, run }), [label, run]);

  return (
    <BusyContext.Provider value={value}>
      {children}
      {label ? (
        <div className="loader-overlay" role="status" aria-live="polite">
          <div className="loader-card">
            <span className="spinner" aria-hidden="true" />
            <p>{label}</p>
          </div>
        </div>
      ) : null}
    </BusyContext.Provider>
  );
}

export function useBusy() {
  return useContext(BusyContext);
}
