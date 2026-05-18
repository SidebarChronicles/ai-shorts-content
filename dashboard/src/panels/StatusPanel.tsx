import { useEffect, useState } from "react";
import {
  loadChannelPhase,
  loadCrossPostStatus,
  loadElevenlabsUsage,
  loadQueueDepth,
  loadReplicateUsage,
} from "../lib/loadData";
import type {
  ChannelPhase,
  CrossPostStatus,
  ElevenlabsUsage,
  Manifest,
  QueueDepth,
  ReplicateUsage,
} from "../lib/types";

interface Props {
  manifest: Manifest;
}

function currentYearMonth(): string {
  const d = new Date();
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function clamp(n: number, lo = 0, hi = 1): number {
  return Math.max(lo, Math.min(hi, n));
}

function fillClass(ratio: number): string {
  if (ratio >= 0.9) return "bar-fill bad";
  if (ratio >= 0.7) return "bar-fill warn";
  return "bar-fill good";
}

export default function StatusPanel(_: Props) {
  const [phase, setPhase] = useState<ChannelPhase | null>(null);
  const [queue, setQueue] = useState<QueueDepth>({});
  const [cross, setCross] = useState<CrossPostStatus>({});
  const [el, setEl] = useState<ElevenlabsUsage>({});
  const [rep, setRep] = useState<ReplicateUsage>({});
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      loadChannelPhase(),
      loadQueueDepth(),
      loadCrossPostStatus(),
      loadElevenlabsUsage(),
      loadReplicateUsage(),
    ])
      .then(([p, q, c, e, r]) => {
        setPhase(p);
        setQueue(q);
        setCross(c);
        setEl(e);
        setRep(r);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="error">{err}</div>;
  if (!phase) return <div className="loading">Loading status…</div>;

  const ym = currentYearMonth();
  const elChars = el[ym]?.chars ?? 0;
  const repUsd = rep[ym]?.usd ?? 0;
  const elRatio = clamp(elChars / phase.el_budget_softcap_chars);
  const repRatio = clamp(repUsd / phase.story_budget_softcap_usd);

  // Today's posts by youtube date
  const todayISO = new Date().toISOString().slice(0, 10);
  const today = Object.entries(cross).filter(([, r]) => r.youtube && r.youtube.startsWith(todayISO));
  const totalDailyTarget = phase.videos_per_fire * phase.fires_per_day;

  // Total queue across all verticals
  const totalQueue = Object.values(queue).reduce((a, b) => a + b, 0);

  const verticalOrder = Object.keys(queue).sort((a, b) => (queue[b] ?? 0) - (queue[a] ?? 0));

  return (
    <>
      <div className="grid cols-4">
        <div className="card">
          <h3>Phase</h3>
          <div className="kpi">{phase.phase}</div>
          <div className="kpi-sub">
            {phase.phase_name.replace(/_/g, " ")} · day {phase.day_index}
          </div>
        </div>
        <div className="card">
          <h3>Daily target</h3>
          <div className="kpi">{totalDailyTarget}</div>
          <div className="kpi-sub">
            {phase.videos_per_fire}/fire × {phase.fires_per_day} fires
          </div>
        </div>
        <div className="card">
          <h3>Posted today</h3>
          <div className="kpi">{today.length}</div>
          <div className="kpi-sub">of {totalDailyTarget} target</div>
        </div>
        <div className="card">
          <h3>Queue total</h3>
          <div className="kpi">{totalQueue}</div>
          <div className="kpi-sub">{verticalOrder.length} verticals</div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>Queue depth by vertical</h3>
          {verticalOrder.map((v) => {
            const count = queue[v] ?? 0;
            const max = Math.max(...Object.values(queue), 1);
            return (
              <div key={v}>
                <div className="row">
                  <span className="label">{v}</span>
                  <span>{count}</span>
                </div>
                <div className="bar">
                  <div className="bar-fill" style={{ width: `${(count / max) * 100}%` }} />
                </div>
              </div>
            );
          })}
        </div>

        <div className="card">
          <h3>Budget caps · {ym}</h3>
          <div className="row">
            <span className="label">ElevenLabs chars</span>
            <span>
              {elChars.toLocaleString()} / {phase.el_budget_softcap_chars.toLocaleString()}
            </span>
          </div>
          <div className="bar">
            <div className={fillClass(elRatio)} style={{ width: `${elRatio * 100}%` }} />
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <span className="label">Replicate USD (story)</span>
            <span>
              ${repUsd.toFixed(2)} / ${phase.story_budget_softcap_usd}
            </span>
          </div>
          <div className="bar">
            <div className={fillClass(repRatio)} style={{ width: `${repRatio * 100}%` }} />
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <span className="label">EL tier</span>
            <span>{phase.el_tier}</span>
          </div>
          <div className="row">
            <span className="label">Priority vertical</span>
            <span>{phase.priority_verticals.join(", ") || "—"}</span>
          </div>
        </div>
      </div>

      {today.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Posted today ({todayISO})</h3>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>YouTube</th>
                <th>TikTok</th>
                <th>Instagram</th>
              </tr>
            </thead>
            <tbody>
              {today.map(([id, r]) => (
                <tr key={id}>
                  <td>{id}</td>
                  <td>
                    {r.youtube ? new Date(r.youtube).toLocaleTimeString() : "—"}
                  </td>
                  <td>{statusBadge(r.tiktok)}</td>
                  <td>{statusBadge(r.instagram)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function statusBadge(val: string | null) {
  if (!val) return <span className="badge pending">pending</span>;
  if (val === "__skipped__") return <span className="badge skipped">skipped</span>;
  return <span className="badge posted">{new Date(val).toLocaleTimeString()}</span>;
}
