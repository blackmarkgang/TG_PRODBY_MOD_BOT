import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        ready: () => void;
        expand: () => void;
      };
    };
  }
}

type Application = {
  id: number;
  status: string;
  age: number | null;
  music_role: string | null;
  answers: Record<string, string>;
  created_at: string;
  user: {
    telegram_id: number;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
  };
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [error, setError] = useState<string | null>(null);
  const initData = useMemo(() => window.Telegram?.WebApp?.initData ?? "", []);

  useEffect(() => {
    window.Telegram?.WebApp?.ready();
    window.Telegram?.WebApp?.expand();
  }, []);

  async function loadApplications() {
    setError(null);
    const response = await fetch(`${apiBaseUrl}/applications`, {
      headers: { Authorization: `tma ${initData}` },
    });
    if (!response.ok) {
      setError(`Failed to load applications: ${response.status}`);
      return;
    }
    setApplications(await response.json());
  }

  async function review(id: number, action: "approve" | "reject") {
    const response = await fetch(`${apiBaseUrl}/applications/${id}/${action}`, {
      method: "POST",
      headers: {
        Authorization: `tma ${initData}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ comment: null }),
    });
    if (!response.ok) {
      setError(`Failed to ${action}: ${response.status}`);
      return;
    }
    await loadApplications();
  }

  useEffect(() => {
    void loadApplications();
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Prod.by Admin</h1>
          <p>Applications queue</p>
        </div>
        <button onClick={loadApplications}>Refresh</button>
      </header>

      {error && <div className="error">{error}</div>}
      {!initData && (
        <div className="notice">
          Open this page from Telegram Mini App to authenticate admin requests.
        </div>
      )}

      <section className="grid">
        {applications.map((item) => (
          <article className="card" key={item.id}>
            <div className="card-head">
              <strong>#{item.id}</strong>
              <span className={`status ${item.status}`}>{item.status}</span>
            </div>
            <div className="meta">
              <span>{item.user.first_name ?? "Unknown"}</span>
              <span>@{item.user.username ?? "no_username"}</span>
              <span>{item.age ?? "-"} years</span>
              <span>{item.music_role ?? "no role"}</span>
            </div>
            <dl>
              {Object.entries(item.answers).map(([key, value]) => (
                <React.Fragment key={key}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </React.Fragment>
              ))}
            </dl>
            {item.status === "pending" && (
              <div className="actions">
                <button className="approve" onClick={() => review(item.id, "approve")}>
                  Approve
                </button>
                <button className="reject" onClick={() => review(item.id, "reject")}>
                  Reject
                </button>
              </div>
            )}
          </article>
        ))}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);

