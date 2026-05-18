import { useEffect, useState } from "react";
import { loadManifest } from "./lib/loadData";
import type { Manifest } from "./lib/types";
import StatusPanel from "./panels/StatusPanel";
import AnalyticsPanel from "./panels/AnalyticsPanel";
import CostsPanel from "./panels/CostsPanel";

type Tab = "status" | "analytics" | "costs";

export default function App() {
  const [tab, setTab] = useState<Tab>("status");
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    loadManifest()
      .then(setManifest)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="shell"><div className="error">Failed to load manifest: {err}<br/>Run <code>npm run sync</code> first.</div></div>;
  if (!manifest) return <div className="shell"><div className="loading">Loading…</div></div>;

  const generatedAt = new Date(manifest.generated_at).toLocaleString();

  return (
    <div className="shell">
      <header className="header">
        <h1>AI Shorts — Channel Dashboard</h1>
        <span className="gen">Data synced: {generatedAt}</span>
      </header>

      <nav className="tabs">
        <button className={tab === "status" ? "active" : ""} onClick={() => setTab("status")}>
          Status
        </button>
        <button className={tab === "analytics" ? "active" : ""} onClick={() => setTab("analytics")}>
          Analytics
        </button>
        <button className={tab === "costs" ? "active" : ""} onClick={() => setTab("costs")}>
          Costs
        </button>
      </nav>

      {tab === "status" && <StatusPanel manifest={manifest} />}
      {tab === "analytics" && <AnalyticsPanel manifest={manifest} />}
      {tab === "costs" && <CostsPanel manifest={manifest} />}
    </div>
  );
}
