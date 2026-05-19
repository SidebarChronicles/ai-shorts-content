import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  loadAllPosted,
  loadAnalyticsReport,
  loadChannelPhase,
  loadElevenlabsUsage,
  loadReplicateUsage,
} from "../lib/loadData";
import { metricsOf } from "../lib/types";
import type {
  AnalyticsReport,
  ChannelPhase,
  ElevenlabsUsage,
  Manifest,
  PostedLedger,
  ReplicateUsage,
} from "../lib/types";
import {
  CLAUDE_MAX_USD_PER_MONTH,
  POSTFAST_USD_PER_MONTH,
  SERVICE_COLORS,
} from "../lib/constants";

interface Props {
  manifest: Manifest;
}

function currentYearMonth(): string {
  const d = new Date();
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function ym(d: Date): string {
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

export default function CostsPanel({ manifest }: Props) {
  const [phase, setPhase] = useState<ChannelPhase | null>(null);
  const [el, setEl] = useState<ElevenlabsUsage>({});
  const [rep, setRep] = useState<ReplicateUsage>({});
  const [posted, setPosted] = useState<Record<string, PostedLedger>>({});
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    // Promise.allSettled so one missing JSON (typically channel_phase.json,
    // which has no empty fallback in loadData.ts) doesn't blank the entire panel.
    Promise.allSettled([
      loadChannelPhase(),
      loadElevenlabsUsage(),
      loadReplicateUsage(),
      loadAllPosted(manifest.verticals_with_posts),
      manifest.analytics_reports[0]
        ? loadAnalyticsReport(manifest.analytics_reports[0])
        : Promise.resolve(null as AnalyticsReport | null),
    ]).then(([pRes, eRes, rRes, postsRes, rptRes]) => {
      if (pRes.status === "fulfilled") setPhase(pRes.value);
      else {
        // eslint-disable-next-line no-console
        console.warn("[dashboard] channel_phase.json failed to load:", pRes.reason);
        setErr(String(pRes.reason));  // phase is required — surface the failure
      }
      if (eRes.status === "fulfilled") setEl(eRes.value);
      // eslint-disable-next-line no-console
      else console.warn("[dashboard] elevenlabs_usage.json failed to load:", eRes.reason);
      if (rRes.status === "fulfilled") setRep(rRes.value);
      // eslint-disable-next-line no-console
      else console.warn("[dashboard] replicate_usage.json failed to load:", rRes.reason);
      if (postsRes.status === "fulfilled") setPosted(postsRes.value);
      // eslint-disable-next-line no-console
      else console.warn("[dashboard] posted ledgers failed to load:", postsRes.reason);
      if (rptRes.status === "fulfilled") setReport(rptRes.value);
      // eslint-disable-next-line no-console
      else console.warn("[dashboard] analytics report failed to load:", rptRes.reason);
    });
  }, [manifest]);

  const months = useMemo(() => {
    const set = new Set<string>([currentYearMonth(), ...Object.keys(el), ...Object.keys(rep)]);
    return Array.from(set).sort();
  }, [el, rep]);

  const monthSeries = useMemo(() => {
    return months.map((m) => ({
      month: m,
      Claude: CLAUDE_MAX_USD_PER_MONTH,
      ElevenLabs: el[m]?.usd ?? 0,
      Replicate: rep[m]?.usd ?? 0,
      PostFast: POSTFAST_USD_PER_MONTH,
    }));
  }, [months, el, rep]);

  if (err) return <div className="error">{err}</div>;
  if (!phase) return <div className="loading">Loading costs…</div>;

  const cym = currentYearMonth();
  const elUsd = el[cym]?.usd ?? 0;
  const elChars = el[cym]?.chars ?? 0;
  const repUsd = rep[cym]?.usd ?? 0;
  const totalUsd = CLAUDE_MAX_USD_PER_MONTH + elUsd + repUsd + POSTFAST_USD_PER_MONTH;

  // Count videos posted this month across all verticals (by uploaded_at)
  let postsThisMonth = 0;
  for (const ledger of Object.values(posted)) {
    for (const rec of Object.values(ledger)) {
      if (rec.uploaded_at && ym(new Date(rec.uploaded_at)) === cym) postsThisMonth++;
    }
  }

  const costPerVideo = postsThisMonth > 0 ? totalUsd / postsThisMonth : 0;

  // From latest analytics report
  const rollup = report ? metricsOf(report.channel_rollup) : metricsOf(undefined);
  const rollupViews = rollup.views;
  const rollupSubs = rollup.subscribersGained;
  const costPer1kViews = rollupViews > 0 ? (totalUsd / rollupViews) * 1000 : 0;
  const costPerSub = rollupSubs > 0 ? totalUsd / rollupSubs : 0;

  const elRatio = clamp(elChars / phase.el_budget_softcap_chars);
  const repRatio = clamp(repUsd / phase.story_budget_softcap_usd);

  return (
    <>
      <div className="grid cols-4">
        <Kpi label={`Total spend · ${cym}`} value={`$${totalUsd.toFixed(2)}`} sub={`${postsThisMonth} videos posted`} />
        <Kpi label="Cost / video" value={costPerVideo > 0 ? `$${costPerVideo.toFixed(2)}` : "—"} sub="all services / posts" />
        <Kpi label="Cost / 1k views" value={costPer1kViews > 0 ? `$${costPer1kViews.toFixed(2)}` : "—"} sub={`${rollupViews.toLocaleString()} views`} />
        <Kpi label="Cost / sub" value={costPerSub > 0 ? `$${costPerSub.toFixed(2)}` : "—"} sub={`+${rollupSubs} subs`} />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>Breakdown · {cym}</h3>
          <Line label="Claude Max" usd={CLAUDE_MAX_USD_PER_MONTH} color={SERVICE_COLORS.claudeMax} sub="$100/mo flat subscription" />
          <Line label="ElevenLabs" usd={elUsd} color={SERVICE_COLORS.elevenlabs} sub={`${elChars.toLocaleString()} chars · ${phase.el_tier} tier`} />
          <Line label="Replicate" usd={repUsd} color={SERVICE_COLORS.replicate} sub={`${rep[cym]?.flux_images ?? 0} flux · ${rep[cym]?.pika_clip_seconds ?? 0}s pika`} />
          <Line label="PostFast" usd={POSTFAST_USD_PER_MONTH} color={SERVICE_COLORS.postfast} sub="~$15/mo TikTok+IG cross-post" />
          <div className="row" style={{ marginTop: 12 }}>
            <strong>Total</strong>
            <strong>${totalUsd.toFixed(2)}</strong>
          </div>
        </div>

        <div className="card">
          <h3>Budget caps · {cym}</h3>
          <div className="row">
            <span className="label">EL chars</span>
            <span>
              {elChars.toLocaleString()} / {phase.el_budget_softcap_chars.toLocaleString()}
            </span>
          </div>
          <div className="bar">
            <div className={fillClass(elRatio)} style={{ width: `${elRatio * 100}%` }} />
          </div>
          <div className="kpi-sub" style={{ marginTop: 4 }}>{(elRatio * 100).toFixed(1)}% of soft cap</div>

          <div className="row" style={{ marginTop: 16 }}>
            <span className="label">Replicate USD (story)</span>
            <span>
              ${repUsd.toFixed(2)} / ${phase.story_budget_softcap_usd}
            </span>
          </div>
          <div className="bar">
            <div className={fillClass(repRatio)} style={{ width: `${repRatio * 100}%` }} />
          </div>
          <div className="kpi-sub" style={{ marginTop: 4 }}>{(repRatio * 100).toFixed(1)}% of soft cap</div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Monthly stacked spend</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={monthSeries} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#262c3a" />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#8a91a3" }} />
            <YAxis tick={{ fontSize: 11, fill: "#8a91a3" }} unit="$" />
            <Tooltip
              contentStyle={{ background: "#141821", border: "1px solid #262c3a", borderRadius: 6 }}
              formatter={(v: number) => `$${v.toFixed(2)}`}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="Claude" stackId="a" fill={SERVICE_COLORS.claudeMax} />
            <Bar dataKey="ElevenLabs" stackId="a" fill={SERVICE_COLORS.elevenlabs} />
            <Bar dataKey="Replicate" stackId="a" fill={SERVICE_COLORS.replicate} />
            <Bar dataKey="PostFast" stackId="a" fill={SERVICE_COLORS.postfast} />
          </BarChart>
        </ResponsiveContainer>
        <div className="kpi-sub" style={{ marginTop: 8 }}>
          Claude Max + PostFast are flat monthly subscriptions. ElevenLabs + Replicate are metered.
        </div>
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

function Line({ label, usd, color, sub }: { label: string; usd: number; color: string; sub: string }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div className="row" style={{ borderTop: "none", paddingTop: 0 }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: color, display: "inline-block" }} />
          {label}
        </span>
        <span>${usd.toFixed(2)}</span>
      </div>
      <div className="kpi-sub">{sub}</div>
    </div>
  );
}
