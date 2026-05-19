import React, { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { loadAnalyticsReport } from "../lib/loadData";
import { metricsOf } from "../lib/types";
import type { AnalyticsReport, Manifest, VideoAnalytics } from "../lib/types";

interface Props {
  manifest: Manifest;
}

type SortKey = "uploaded_at" | "views" | "averageViewPercentage" | "subscribersGained";

const YPP_SUBS_GOAL = 1000;
const YPP_VIEWS_GOAL = 10_000_000;
const YPP_WATCH_HOURS_GOAL = 4000;

export default function AnalyticsPanel({ manifest }: Props) {
  const [reportKey, setReportKey] = useState<string>(manifest.analytics_reports[0] ?? "");
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("uploaded_at");
  const [sortDesc, setSortDesc] = useState(true);

  useEffect(() => {
    if (!reportKey) return;
    setReport(null);
    loadAnalyticsReport(reportKey)
      .then(setReport)
      .catch((e) => setErr(String(e)));
  }, [reportKey]);

  const sortedVideos = useMemo(() => {
    if (!report) return [];
    const entries = Object.entries(report.videos);
    entries.sort(([, a], [, b]) => {
      const va = getSortVal(a, sortKey);
      const vb = getSortVal(b, sortKey);
      return sortDesc ? vb - va : va - vb;
    });
    return entries;
  }, [report, sortKey, sortDesc]);

  const chartData = useMemo(() => {
    if (!report) return [];
    return Object.entries(report.videos).map(([id, v]) => {
      const m = metricsOf(v.metrics);
      return {
        id: shortId(id),
        views: m.views,
        retention: m.averageViewPercentage * 100,
      };
    });
  }, [report]);

  if (err) return <div className="error">{err}</div>;
  if (manifest.analytics_reports.length === 0)
    return <div className="loading">No analytics reports synced yet.</div>;
  if (!report) return <div className="loading">Loading analytics…</div>;

  const r = metricsOf(report.channel_rollup);
  const watchHours = r.estimatedMinutesWatched / 60;

  // YPP estimates — channel-rollup doesn't have subs total, only delta. Show delta.
  const subsRatio = Math.min(1, r.subscribersGained / YPP_SUBS_GOAL);
  const viewsRatio = Math.min(1, r.views / YPP_VIEWS_GOAL);
  const watchRatio = Math.min(1, watchHours / YPP_WATCH_HOURS_GOAL);

  function toggleSort(k: SortKey) {
    if (sortKey === k) setSortDesc((d) => !d);
    else {
      setSortKey(k);
      setSortDesc(true);
    }
  }

  function onSortKey(e: React.KeyboardEvent<HTMLTableCellElement>, k: SortKey) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleSort(k);
    }
  }

  return (
    <>
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <h3 style={{ margin: 0 }}>Report</h3>
          <select
            value={reportKey}
            onChange={(e) => setReportKey(e.target.value)}
            style={{
              background: "var(--panel-2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              padding: "6px 10px",
              borderRadius: 6,
            }}
          >
            {manifest.analytics_reports.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <span className="kpi-sub" style={{ marginTop: 0 }}>
            Window: {report.window.start} → {report.window.end}
          </span>
        </div>
      </div>

      <div className="grid cols-4">
        <Kpi label="Views" value={r.views.toLocaleString()} />
        <Kpi label="Watch hours" value={watchHours.toFixed(1)} sub={`${r.estimatedMinutesWatched.toLocaleString()} min`} />
        <Kpi label="Subs Δ" value={String(r.subscribersGained - r.subscribersLost)} sub={`+${r.subscribersGained} / -${r.subscribersLost}`} />
        <Kpi label="Avg view %" value={`${(r.averageViewPercentage * 100).toFixed(1)}%`} sub={`avg dur ${r.averageViewDuration.toFixed(1)}s`} />
      </div>

      <div className="grid cols-3" style={{ marginTop: 16 }}>
        <YppGauge label="Subscribers (delta)" current={r.subscribersGained} goal={YPP_SUBS_GOAL} ratio={subsRatio} />
        <YppGauge label="Shorts views (90d proxy)" current={r.views} goal={YPP_VIEWS_GOAL} ratio={viewsRatio} />
        <YppGauge label="Watch hours" current={watchHours} goal={YPP_WATCH_HOURS_GOAL} ratio={watchRatio} suffix="h" />
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Views vs retention by video</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#262c3a" />
            <XAxis dataKey="id" tick={{ fontSize: 11, fill: "#8a91a3" }} />
            <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "#8a91a3" }} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: "#8a91a3" }} unit="%" />
            <Tooltip contentStyle={{ background: "#141821", border: "1px solid #262c3a", borderRadius: 6 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar yAxisId="left" dataKey="views" fill="#7aa2f7" name="Views" />
            <Bar yAxisId="right" dataKey="retention" fill="#5eead4" name="Avg view %">
              {chartData.map((d, i) => (
                <Cell key={d.id ?? i} fill="#5eead4" />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Per-video</h3>
        <table>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col" role="button" tabIndex={0} aria-sort={ariaSort(sortKey, "uploaded_at", sortDesc)} onClick={() => toggleSort("uploaded_at")} onKeyDown={(e) => onSortKey(e, "uploaded_at")}>Uploaded {sortArrow(sortKey, "uploaded_at", sortDesc)}</th>
              <th scope="col" role="button" tabIndex={0} aria-sort={ariaSort(sortKey, "views", sortDesc)} onClick={() => toggleSort("views")} onKeyDown={(e) => onSortKey(e, "views")}>Views {sortArrow(sortKey, "views", sortDesc)}</th>
              <th scope="col" role="button" tabIndex={0} aria-sort={ariaSort(sortKey, "averageViewPercentage", sortDesc)} onClick={() => toggleSort("averageViewPercentage")} onKeyDown={(e) => onSortKey(e, "averageViewPercentage")}>Avg view % {sortArrow(sortKey, "averageViewPercentage", sortDesc)}</th>
              <th scope="col" role="button" tabIndex={0} aria-sort={ariaSort(sortKey, "subscribersGained", sortDesc)} onClick={() => toggleSort("subscribersGained")} onKeyDown={(e) => onSortKey(e, "subscribersGained")}>Subs Δ {sortArrow(sortKey, "subscribersGained", sortDesc)}</th>
              <th scope="col">Watch</th>
            </tr>
          </thead>
          <tbody>
            {sortedVideos.map(([id, v]) => {
              const m = metricsOf(v.metrics);
              return (
                <tr key={id}>
                  <td>{id}</td>
                  <td>{v.uploaded_at ? new Date(v.uploaded_at).toLocaleDateString() : "—"}</td>
                  <td>{m.views.toLocaleString()}</td>
                  <td>{(m.averageViewPercentage * 100).toFixed(1)}%</td>
                  <td>{m.subscribersGained - m.subscribersLost}</td>
                  <td>
                    <a href={v.watch_url} target="_blank" rel="noreferrer">
                      open
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card">
      <h3>{label}</h3>
      <div className="kpi">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

function YppGauge({
  label,
  current,
  goal,
  ratio,
  suffix = "",
}: {
  label: string;
  current: number;
  goal: number;
  ratio: number;
  suffix?: string;
}) {
  return (
    <div className="card">
      <h3>{label}</h3>
      <div className="row" style={{ borderTop: "none", paddingTop: 0 }}>
        <span className="label">progress</span>
        <span>
          {formatNum(current)}
          {suffix} / {formatNum(goal)}
          {suffix}
        </span>
      </div>
      <div className="bar">
        <div
          className={ratio >= 1 ? "bar-fill good" : "bar-fill"}
          style={{ width: `${ratio * 100}%` }}
        />
      </div>
      <div className="kpi-sub" style={{ marginTop: 8 }}>
        {(ratio * 100).toFixed(1)}% of goal
      </div>
    </div>
  );
}

function formatNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toFixed(n < 10 ? 1 : 0);
}

function shortId(id: string): string {
  return id.length > 16 ? id.slice(0, 14) + "…" : id;
}

function getSortVal(v: VideoAnalytics, k: SortKey): number {
  if (k === "uploaded_at") return v.uploaded_at ? new Date(v.uploaded_at).getTime() : 0;
  const m = metricsOf(v.metrics);
  if (k === "views") return m.views;
  if (k === "averageViewPercentage") return m.averageViewPercentage;
  return m.subscribersGained - m.subscribersLost;
}

function sortArrow(active: SortKey, k: SortKey, desc: boolean): string {
  if (active !== k) return "";
  return desc ? " ↓" : " ↑";
}

function ariaSort(active: SortKey, k: SortKey, desc: boolean): "ascending" | "descending" | "none" {
  if (active !== k) return "none";
  return desc ? "descending" : "ascending";
}
