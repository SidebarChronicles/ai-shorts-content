#!/usr/bin/env node
// Copies/derives JSON from output/ + queue dirs into docs/data/ for the dashboard.
// Idempotent. Safe to re-run. Run before `vite build` and `vite dev`.

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DASHBOARD_DIR = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(DASHBOARD_DIR, "..");
// Write to Vite's publicDir so the data is bundled into docs/ at build time,
// and served at `${BASE_URL}data/...` during `vite dev`.
const OUT_DIR = path.join(DASHBOARD_DIR, "public", "data");

async function ensureDir(p) {
  await fs.mkdir(p, { recursive: true });
}

async function exists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function copyJson(src, destName) {
  const dest = path.join(OUT_DIR, destName);
  if (!(await exists(src))) {
    await fs.writeFile(dest, "{}", "utf8");
    return false;
  }
  await fs.copyFile(src, dest);
  return true;
}

// Map vertical name → ledger dir name. TrueCrime uses bare "videos/".
const VERTICAL_VIDEO_DIRS = {
  truecrime: "videos",
  story: "story_videos",
  games: "game_videos",
  movies: "movie_videos",
  mystery: "mystery_videos",
  mythology: "mythology_videos",
  topx: "topx_videos",
  finance: "finance_videos",
};

// Map vertical name → queue dir.
const VERTICAL_QUEUE_DIRS = {
  truecrime: "case_queue",
  story: "story_queue",
  games: "game_queue",
  movies: "movie_queue",
  mystery: "mystery_queue",
  mythology: "mythology_queue",
  topx: "topx_queue",
  finance: "finance_queue",
};

async function syncPosted() {
  const postedDir = path.join(OUT_DIR, "posted");
  await ensureDir(postedDir);
  const verticalsWithPosts = [];
  for (const [vertical, dirName] of Object.entries(VERTICAL_VIDEO_DIRS)) {
    const src = path.join(REPO_ROOT, "output", dirName, "_posted.json");
    const dest = path.join(postedDir, `${vertical}.json`);
    if (await exists(src)) {
      await fs.copyFile(src, dest);
      verticalsWithPosts.push(vertical);
    } else {
      await fs.writeFile(dest, "{}", "utf8");
    }
  }
  return verticalsWithPosts;
}

async function syncQueueDepth() {
  const depth = {};
  for (const [vertical, dirName] of Object.entries(VERTICAL_QUEUE_DIRS)) {
    const dir = path.join(REPO_ROOT, dirName);
    if (!(await exists(dir))) {
      depth[vertical] = 0;
      continue;
    }
    const files = await fs.readdir(dir);
    depth[vertical] = files.filter((f) => f.endsWith(".md")).length;
  }
  await fs.writeFile(
    path.join(OUT_DIR, "queue_depth.json"),
    JSON.stringify(depth, null, 2),
    "utf8",
  );
}

async function syncAnalytics() {
  const srcDir = path.join(REPO_ROOT, "output", "analytics");
  const destDir = path.join(OUT_DIR, "analytics");
  await ensureDir(destDir);
  if (!(await exists(srcDir))) return [];
  const files = await fs.readdir(srcDir);
  const reports = [];
  for (const f of files) {
    if (!f.startsWith("report_") || !f.endsWith(".json")) continue;
    await fs.copyFile(path.join(srcDir, f), path.join(destDir, f));
    // Extract date (or date_variant) between "report_" and ".json"
    reports.push(f.slice("report_".length, -".json".length));
  }
  // Sort descending — newest first
  reports.sort().reverse();
  return reports;
}

async function main() {
  console.log(`[sync] repo root: ${REPO_ROOT}`);
  await ensureDir(OUT_DIR);

  // Top-level singletons
  await copyJson(path.join(REPO_ROOT, "output", ".channel_phase.json"), "channel_phase.json");
  await copyJson(path.join(REPO_ROOT, "output", "replicate_usage.json"), "replicate_usage.json");
  await copyJson(path.join(REPO_ROOT, "output", "elevenlabs_usage.json"), "elevenlabs_usage.json");
  await copyJson(path.join(REPO_ROOT, "output", "cross_post_status.json"), "cross_post_status.json");

  const verticalsWithPosts = await syncPosted();
  await syncQueueDepth();
  const reports = await syncAnalytics();

  const manifest = {
    generated_at: new Date().toISOString(),
    analytics_reports: reports,
    verticals_with_posts: verticalsWithPosts,
  };
  await fs.writeFile(path.join(OUT_DIR, "manifest.json"), JSON.stringify(manifest, null, 2), "utf8");

  console.log(`[sync] wrote ${reports.length} analytics reports`);
  console.log(`[sync] verticals with posts: ${verticalsWithPosts.join(", ") || "(none)"}`);
  console.log(`[sync] done → ${OUT_DIR}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
