import type {
  AnalyticsReport,
  ChannelPhase,
  CrossPostStatus,
  ElevenlabsUsage,
  Manifest,
  PostedLedger,
  QueueDepth,
  ReplicateUsage,
} from "./types";

const dataUrl = (path: string) => `${import.meta.env.BASE_URL}data/${path}`;

async function fetchJson<T>(path: string, fallback: T | null = null): Promise<T> {
  const res = await fetch(dataUrl(path));
  if (!res.ok) {
    if (fallback !== null) return fallback;
    throw new Error(`Failed to load ${path}: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function loadManifest(): Promise<Manifest> {
  return fetchJson<Manifest>("manifest.json");
}

export async function loadChannelPhase(): Promise<ChannelPhase> {
  return fetchJson<ChannelPhase>("channel_phase.json");
}

export async function loadCrossPostStatus(): Promise<CrossPostStatus> {
  return fetchJson<CrossPostStatus>("cross_post_status.json", {});
}

export async function loadQueueDepth(): Promise<QueueDepth> {
  return fetchJson<QueueDepth>("queue_depth.json", {});
}

export async function loadElevenlabsUsage(): Promise<ElevenlabsUsage> {
  return fetchJson<ElevenlabsUsage>("elevenlabs_usage.json", {});
}

export async function loadReplicateUsage(): Promise<ReplicateUsage> {
  return fetchJson<ReplicateUsage>("replicate_usage.json", {});
}

export async function loadPosted(vertical: string): Promise<PostedLedger> {
  return fetchJson<PostedLedger>(`posted/${vertical}.json`, {});
}

export async function loadAnalyticsReport(date: string): Promise<AnalyticsReport> {
  return fetchJson<AnalyticsReport>(`analytics/report_${date}.json`);
}

export async function loadAllPosted(verticals: string[]): Promise<Record<string, PostedLedger>> {
  const entries = await Promise.all(
    verticals.map(async (v) => [v, await loadPosted(v)] as const),
  );
  return Object.fromEntries(entries);
}
