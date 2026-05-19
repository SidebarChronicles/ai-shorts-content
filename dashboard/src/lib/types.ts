export interface ChannelPhase {
  phase: number;
  phase_name: string;
  start_date: string;
  end_date_planned: string;
  day_index: number;
  kept_verticals: string[];
  priority_verticals: string[];
  priority_until_count: number;
  videos_per_fire: number;
  fires_per_day: number;
  el_budget_softcap_chars: number;
  el_tier: string;
  story_budget_softcap_usd: number;
  story_subgenre_voices: Record<string, string>;
  story_subgenre_rotation: string[];
}

export interface VideoMetrics {
  views?: number;
  estimatedMinutesWatched?: number;
  averageViewDuration?: number;
  averageViewPercentage?: number;
  subscribersGained?: number;
  subscribersLost?: number;
  likes?: number;
  dislikes?: number;
  shares?: number;
  comments?: number;
  _no_data?: boolean;
}

/** Normalize a possibly-empty metrics record to numeric defaults. */
export function metricsOf(m: VideoMetrics | undefined): Required<Omit<VideoMetrics, "_no_data">> {
  return {
    views: m?.views ?? 0,
    estimatedMinutesWatched: m?.estimatedMinutesWatched ?? 0,
    averageViewDuration: m?.averageViewDuration ?? 0,
    averageViewPercentage: m?.averageViewPercentage ?? 0,
    subscribersGained: m?.subscribersGained ?? 0,
    subscribersLost: m?.subscribersLost ?? 0,
    likes: m?.likes ?? 0,
    dislikes: m?.dislikes ?? 0,
    shares: m?.shares ?? 0,
    comments: m?.comments ?? 0,
  };
}

export interface VideoAnalytics {
  metrics: VideoMetrics;
  retention_curve: Array<{ elapsed_video_time_ratio: number; audience_watch_ratio: number }>;
  scheduled_publish: string;
  // Nullable: pipeline may omit when a video is scheduled but not yet published.
  // AnalyticsPanel + getSortVal already guard with `v.uploaded_at ?`; aligning the type.
  uploaded_at: string | null;
  video_id: string;
  watch_url: string;
}

export interface AnalyticsReport {
  generated_at: string;
  window: { start: string; end: string };
  channel_rollup: VideoMetrics;
  videos: Record<string, VideoAnalytics>;
}

export interface PostedRecord {
  scheduled_publish: string;
  uploaded_at: string;
  video_id: string;
  watch_url: string;
}

export type PostedLedger = Record<string, PostedRecord>;

export interface CrossPostRecord {
  instagram: string | null;
  tiktok: string | null;
  tiktok_gate: string;
  tiktok_retention_pct: number | null;
  videos_dir: string;
  youtube: string | null;
}

export type CrossPostStatus = Record<string, CrossPostRecord>;

export interface ElevenlabsUsage {
  [yyyymm: string]: { chars: number; usd: number };
}

export interface ReplicateUsage {
  [yyyymm: string]: { flux_images: number; pika_clip_seconds: number; usd: number };
}

export interface QueueDepth {
  [vertical: string]: number;
}

export interface Manifest {
  generated_at: string;
  analytics_reports: string[];
  verticals_with_posts: string[];
}
