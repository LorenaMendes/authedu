import { useEffect, useState } from "react";

const messages = {
  checking: {
    label: "Checking connection",
    detail: "Sending a health request to the local API…",
  },
  available: {
    label: "API is available",
    detail: "The API process responded successfully.",
  },
  unavailable: {
    label: "API is unavailable",
    detail: "Could not reach the local API. Make sure the backend is running, then try again.",
  },
};

export default function App() {
  const [status, setStatus] = useState("checking");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let ignoreResult = false;

    async function checkHealth() {
      setStatus("checking");

      try {
        const response = await fetch("/api/health");
        if (!response.ok) {
          throw new Error("Health request failed");
        }

        const payload = await response.json();
        if (payload.status !== "ok") {
          throw new Error("Unexpected health response");
        }

        if (!ignoreResult) {
          setStatus("available");
        }
      } catch {
        if (!ignoreResult) {
          setStatus("unavailable");
        }
      }
    }

    void checkHealth();
    return () => {
      ignoreResult = true;
    };
  }, [attempt]);

  const message = messages[status];

  return (
    <main className="page-shell">
      <header className="topbar">
        <div className="brand" aria-label="AuthEdu">
          <span className="brand-mark" aria-hidden="true">A</span>
          <span>AuthEdu</span>
        </div>
        <span className="environment-badge">
          <span className="environment-dot" aria-hidden="true" />
          Local development
        </span>
      </header>

      <section className="content" aria-labelledby="page-title">
        <p className="eyebrow">FOUNDATION · CONNECTIVITY</p>
        <h1 id="page-title">Your API connection</h1>
        <p className="intro">
          A small first check: the browser asks the AuthEdu API whether its process is responding.
        </p>

        <section className={`status-card status-card--${status}`} aria-labelledby="status-heading">
          <div className="status-icon" aria-hidden="true">
            {status === "available" ? "✓" : status === "unavailable" ? "!" : "···"}
          </div>
          <div className="status-copy">
            <p className="card-label" id="status-heading">Service status</p>
            <p className="status-message" role="status" aria-live="polite" aria-atomic="true">
              {message.label}
            </p>
            <p className="status-detail">{message.detail}</p>
          </div>
          <button
            className="retry-button"
            type="button"
            onClick={() => setAttempt((current) => current + 1)}
            disabled={status === "checking"}
          >
            {status === "checking" ? "Checking…" : "Check again"}
          </button>
        </section>

        <div className="request-row" role="group" aria-label="Health check request">
          <span className="method-pill">GET</span>
          <code>/api/health</code>
          <span className="request-note">Forwarded to the backend’s <code>/health</code></span>
        </div>

        <aside className="learning-note">
          <span className="note-mark" aria-hidden="true">i</span>
          <div>
            <h2>What this check means</h2>
            <p>
              It confirms only that the API process can respond. It does not check the database,
              sign you in, or reveal configuration or credentials.
            </p>
          </div>
        </aside>

        <footer className="page-footer">
          <span>AuthEdu is an educational reference, not a production identity provider.</span>
          <span>01 / Foundation</span>
        </footer>
      </section>
    </main>
  );
}
