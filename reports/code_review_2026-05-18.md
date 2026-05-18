# Code Review — 2026-05-18

Hardening pass before daily autonomous schedule. Reviewed 15 Python files (~4,716 LOC).

## Executive summary

- **4 Critical**, **14 High**, **18 Medium**, **2 Low** findings.
- Top 3 fixes that unblock production reliability:
  1. **Atomic state writes** for `output/videos/_posted.json`, `output/elevenlabs_usage.json`, and `game_queue/GG_*.md`. A crash between `read_text()`/`write_text()` in `upload_to_youtube.py:117`, `make_audio_elevenlabs.py:74`, and `game_orchestrator.py:95` will silently truncate the file or lose accounting. Use `tempfile.NamedTemporaryFile` in the same dir + `os.replace()`.
  2. **Idempotency for `mark_posted`** in `upload_to_youtube.py:271`. The upload completes on YouTube and the very next instruction writes `_posted.json`. If the process is killed (or `save_posted` raises) between those two calls, the video is live but the queue still treats it as "READY" — a daily cron will re-upload the same case forever. Mark posted *before* the side-effecting upload, or persist `(case_id, video_id)` immediately after `request.next_chunk()` returns the response, with a recoverable temp marker.
  3. **`Credentials.refresh()` calls have no `RefreshError` handler** in `upload_to_youtube.py:74`, `analyze_performance.py:64`, and `research_top_channels.py:64`. A revoked refresh token (or 7-day "testing" OAuth app expiry) crashes the daily run with a cryptic `RefreshError` stack trace instead of a clear "re-run youtube_oauth_setup.py" message.

Surprisingly good — leave alone:
- `compute_next_slot()` in `upload_to_youtube.py:167` correctly normalizes to local tz via `datetime.now().astimezone()` and walks forward in 1-day steps rather than doing math on naive datetimes. DST-safe.
- The resumable upload retry on 5xx in `upload_to_youtube.py:252–256` is the right pattern.
- The base canvas caching with numpy in `skill/truecrime-short/render_video.py:62–92` is genuinely clean and fast.
- `make_audio_elevenlabs.py` budget gate (`check_budget`) blocks runaway spend before the API call — keep this guard.

## Cross-cutting issues

### OAuth handling (3 scripts)

- **Files:** `upload_to_youtube.py:66–77`, `analyze_performance.py:50–66`, `research_top_channels.py:55–65`
- **Issue:** Each script calls `creds.refresh(Request())` with no try/except. `google.auth.exceptions.RefreshError` fires when (a) the refresh token was revoked, (b) the OAuth client is "Testing" status and the 7-day grace period expired, or (c) the Google account password changed. In autonomous mode this surfaces as an uncaught traceback and the daily cron silently exits non-zero — no actionable message.
- **Recommended fix:** Wrap the refresh in `try: creds.refresh(Request()); except RefreshError as e: sys.exit(f"[FATAL] OAuth refresh failed: {e}\\n  Re-run: python scripts/youtube_oauth_setup.py")`. Bonus: also catch the case where `creds.refresh_token` is `None` (token.json without offline scope) before calling refresh.

### Atomic writes (4 sites)

- **Files:** `upload_to_youtube.py:117` (`save_posted`), `make_audio_elevenlabs.py:74` (`save_usage`), `game_orchestrator.py:95` (`mark_queue_status`), `youtube_oauth_setup.py:78` and `upload_to_youtube.py:75` (`token.json` rewrite after refresh).
- **Issue:** All use `path.write_text(...)`, which truncates immediately then writes. A crash, SIGKILL, or full disk between truncate and write leaves the file empty or partial. `_posted.json` empty → next run re-uploads everything. `elevenlabs_usage.json` empty → budget reset to 0 → silently overspend. `token.json` empty after a refresh crash → daily cron can never auth again until human intervention.
- **Recommended fix:** Helper:
  ```python
  def atomic_write_text(path: Path, data: str) -> None:
      tmp = path.with_suffix(path.suffix + ".tmp")
      tmp.write_text(data)
      os.replace(tmp, path)
  ```
  Apply at all 4 sites. `os.replace` is atomic on POSIX when source and destination are on the same filesystem.

### .env loading (5 implementations)

- **Files:** `make_audio_elevenlabs.py:39–44` (module-level auto-loader), `game_orchestrator.py:208–214` and `:421–426` and `:484–490` (three near-duplicates), and the others rely on `os.environ` only.
- **Issue:** Three problems compound:
  1. **No quote handling.** A `.env` value like `ELEVENLABS_API_KEY="sk-xxx"` is loaded with the literal quotes still attached → API returns 401. The supplied `.env.example` doesn't use quotes today, but the moment a user pastes a Google-style multi-line key with quotes, this silently fails.
  2. **No escape for `=` inside values.** A value containing `=` works (because of `split("=", 1)`) but a comment trailing the value (`KEY=foo  # comment`) is treated as part of the value.
  3. **`os.environ.setdefault` in `make_audio_elevenlabs.py` vs. blind overwrite in `game_orchestrator.py:214`.** The orchestrator clobbers env vars set by the parent shell, which is the wrong precedence — env vars exported by the cron job should win over `.env`.
- **Recommended fix:** Extract a `load_dotenv()` helper in a shared `scripts/_env.py` that (a) strips matched leading/trailing `"` and `'`, (b) ignores anything after an unquoted `#`, (c) uses `setdefault` semantics. Call once at startup; remove the three copies in `game_orchestrator.py`.

### `except Exception` swallows (3 sites)

- `research_games.py:60` (`fetch_steam_list`), `:78` (`fetch_app_details`), `make_audio_elevenlabs.py:304` (ffprobe duration check). The Steam API failures degrade silently to empty lists, which then propagate through `enrich_with_details` and produce zero candidates — the orchestrator's `run_auto` then logs "No QUEUED games found after research" and exits, masking the real (transient) network error.
- **Recommended fix:** In `fetch_steam_list`, log the exception type + message at minimum; keep the empty-list return. Add a sanity check in `run_auto` that distinguishes "no candidates returned" from "API was unreachable" so the daily cron can retry instead of doing nothing.

### Subprocess input handling

- All `subprocess.run` calls use list-form args (not `shell=True`), so direct shell injection is not possible.
- **However**, `--game-id` propagates from `game_queue/GG_*.md` filenames into FFmpeg filter strings (notably `subtitles={ass_path}` in `game_orchestrator.py:265` and the concat list `file '{clip}'` in `skill/game-short/render_game_video.py:173`). FFmpeg's filtergraph parser treats `:`, `'`, `\`, and `,` as metacharacters. A queue filename containing `'` or `:` (legal on macOS) corrupts the filtergraph. Today `research_games.py:251–254` slugifies to `[a-z0-9_]` which mitigates it, but a human-added queue file isn't guaranteed safe.
- **Recommended fix:** In `render_game_video.py`, validate `game_id` matches `^[A-Za-z0-9_]+$` before use; in `game_orchestrator.py` reject queue files whose stem fails the same regex.

### Log hygiene

- `output/game_pipeline.log` (`game_orchestrator.py:49,61`) is append-only forever, no rotation. On a daily schedule this grows ~1 MB/month; not urgent but worth bounding before year-end.
- `step_upload` in `game_orchestrator.py:430` calls `log(result.stdout)` of the entire upload subprocess. That stdout includes the `(refreshed access token)` line but no actual secrets — safe today, but if any subprocess ever logs an API key on error, it lands in `game_pipeline.log` unredacted.
- **Recommended fix:** Use `logging.handlers.RotatingFileHandler` (5 MB × 5 files). Don't log the full stdout of upload subprocesses — keep last 500 chars on error only, just like the other steps.

## Findings by file

### scripts/game_orchestrator.py (551 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| Critical | 94–95 | `mark_queue_status` uses regex replace + `write_text` — not atomic, and the regex `\*\*Status:\*\*\s*\w+` matches the *first* `**Status:**` only; if a queue file contains the word in the description (e.g., quoting a game's "status effects"), the wrong line is rewritten. | Parse the MD into a structured frontmatter at top; atomic write via tempfile + `os.replace`. |
| High | 461–473 | If the pipeline fails mid-flight (e.g., `step_render`), the queue is reset to `QUEUED` but `output/scripts/<game_id>/` is left with partial `clips_portrait/`, partial `captions.ass`, etc. Next retry takes the existence checks at face value (`clips_manifest.json` exists → skip) and continues with stale outputs. | On failure, either preserve a sentinel `.failed` and refuse retry until manually cleared, or wipe `output/scripts/<game_id>/` on failure. Also: invalidate the cached `captions.ass` whenever `game_config.json` mtime is newer. |
| High | 472 | On step failure, status resets to `QUEUED`. If `--auto` runs daily, the same broken queue entry will be retried every day with no backoff and no DLQ. | Add a retry counter to the queue MD (`**Retries:** N`); after 3 consecutive failures move to status `BLOCKED` to require human review. |
| High | 148 / 169 / 188 / 216 / 239 / 273 / 428 | Every `subprocess.run` swallows `subprocess.TimeoutExpired` implicitly by raising — but the timeouts are arbitrary (60–600s) and there's no try/except. A render that exceeds 300s kills the pipeline mid-run; `mark_queue_status(QUEUED)` does *not* fire because the exception unwinds out of `run_pipeline` past the `try`. | Wrap each `subprocess.run` in try/except, log the timeout, and ensure queue status reset always runs (move it to a `finally`). |
| High | 207–214 / 420–426 / 484–490 | Three near-duplicate `.env` loaders. See cross-cutting `.env loading`. | Extract `_env.py:load_dotenv()`. |
| Medium | 198 | `step_generate_audio` checks for `narration_{game_id}.mp3` to skip — but if `game_config.json` was regenerated with a different spoken text, the stale MP3 is silently reused. | Compare `audio_path.stat().st_mtime > config_path.stat().st_mtime` before skipping. |
| Medium | 261–270 | Hardcoded ffmpeg encode params duplicate the comment block in `skill/game-short/render_game_video.py:284–293`. Drift between the two will produce silently inconsistent output. | Move the canonical encode command into a single Python function, call from both. |
| Medium | 76 | `re.search(r"\*\*Status:\*\*\s*(\w+)")` — `\w+` won't match a status containing hyphens (e.g., `IN-PROGRESS`). Locked into single-word statuses by accident. | Use `[A-Z_]+` or document the constraint. |
| Medium | 410–436 | `step_upload` doesn't pass `--schedule auto` so games publish *immediately* on auto-mode. The README implies a 6 PM scheduled slot is the intent. | Add `--schedule auto` to the cmd in `step_upload`, or document that game shorts publish immediately. |
| Low | 56–62 | Open/append/close per log call. Fine at current volume; switch to logging module if scale grows. | Use `logging` with a `RotatingFileHandler`. |

### scripts/fetch_trailer.py (221 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| High | 100–112 | `_download_with_progress` writes directly to `dest` while streaming. A network drop mid-download leaves a truncated `trailer_raw.mp4`; on next run `step_fetch_trailer` sees the file exists and skips re-download, then `select_clips.py` fails on a corrupt input. | Download to `dest.with_suffix(".part")`, then `os.replace(part, dest)` on success. Verify expected `content-length` matches written bytes before the rename. |
| High | 41–47 | No retry on Steam API 5xx. Steam returns 503 occasionally — the script crashes and the orchestrator marks the game `QUEUED`, retrying the entire pipeline on the next cron tick. | Add a tiny retry helper (3 attempts, exponential backoff) for `requests.get` calls. |
| Medium | 53 | `f"...store.steampowered.com/app/{appid}/"` in the error message — this is an *f-string* without the appid being interpolated (the brace is doubled because of the surrounding text). Users get a literal `{appid}` in the error. | Fix the f-string. |
| Medium | 134 | `format=...` string doesn't request mp4 explicitly enough; yt-dlp may emit `.webm` despite `merge_output_format: mp4` if no mp4 audio is available — the rename at line 159 then drops the extension info. | Add a stricter `final_ext` constraint, or detect non-mp4 output and re-mux. |
| Medium | 157–162 | Rename logic `alt.rename(out_path)` will silently overwrite an existing `trailer_raw.mp4` of a different game if anyone passes a wrong `--game-id`. | Refuse if dest exists; let caller delete first. |

### scripts/select_clips.py (222 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| High | 60–74 | `detect_scene_changes` calls FFmpeg with `timeout=120`. On a 90s trailer scene detection takes <5s; on a malformed/empty `trailer_raw.mp4` the call returns instantly with rc=0 and zero detections → `auto_select_clips` returns four near-identical clips at the zone centers (working as designed, but producing a useless short). | After scene detection, assert at least 2 distinct timestamps; otherwise sys.exit with a clear "trailer appears corrupt" error. |
| Medium | 95 | `end = min(start + TARGET_CLIP_LEN, max_end - 1.0, total_duration - 0.5)` — if `total_duration < 1.5`, `end` goes negative and the clip is empty; `extract_clip` then produces a 0-byte mp4 and `ffmpeg -c copy` still returns rc=0. | Add an explicit `assert total_duration > 20` (4 clips need ~40s of source). |
| Medium | 114–129 | `extract_clip` uses stream copy (`-c copy`) without `-avoid_negative_ts make_zero` or `-copyts`. On trailers with B-frames at the cut point, the resulting clip can have audio/video drift or fail to seek cleanly in `render_game_video.py`. | Either accept a re-encode (we're already re-encoding in render step) or add `-avoid_negative_ts make_zero`. |
| Medium | 181–183 | Validation only clamps `end` over duration — doesn't validate `start < end`, `start >= 0`, or numeric types. A bad `--clips` JSON like `{"start": "ten", ...}` raises an opaque `TypeError`. | Add explicit float() coercion + bounds checks. |

### scripts/game_script_writer.py (280 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| High | 112 | `model="claude-sonnet-4-6"` — but the call uses `system=[...]` list form, which is for the new system-cache pattern. This works only if the SDK version supports cached system blocks; older `anthropic` versions error out. There's no pinned version in `requirements_full.txt`. | Pin `anthropic>=0.40.0` (or whichever version introduced cache_control) in requirements; add a try/except around the import to surface a clean error. |
| Medium | 138 | If Claude returns no JSON-shaped response at all (e.g., a refusal), `sys.exit` fires inside the pipeline subprocess — the orchestrator marks `QUEUED` and retries forever. | Catch this case, log the refusal, and signal a non-retryable failure to the orchestrator. |
| Medium | 41–47 | `find_queue_entry` does *prefix*, then *partial* matches — `game_id="01"` would match `GG_01_subnautica2.md`, but also potentially any file containing "01" in its name. Ambiguity is silently resolved to "first match". | Require exact match for autonomous runs; allow fuzzy match only with `--fuzzy`. |
| Medium | 208–210 | `release_label` heuristic uses substring match — `"2026"` in `"early 2026"` returns `OUT NOW`. The current data is fine but the heuristic is wrong. | Replace with a parsed date comparison against `today()`. |

### scripts/make_audio_elevenlabs.py (309 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| Critical | 39–44 | `.env` auto-loader runs at module import. It doesn't strip quotes, doesn't handle inline comments, doesn't unescape `\n`. A user with `ELEVENLABS_API_KEY="sk-xxx"` in their `.env` gets a 401 with the quoted key sent to the API — and the failure mode is opaque (HTTP 401 with no body decode). | See cross-cutting `.env loading`. Also: never log the API key on error, even truncated. |
| High | 78–95 | `check_budget` reads usage, computes projection — but `record_usage` reads → mutates → writes without a lock. If two parallel invocations race (e.g., manual run + scheduled run), one update is lost and the budget guard silently lets total spend exceed `$22`. | Either serialize via `flock`/`fcntl.lockf`, or accept the race (single-host, single-cron) but document the assumption. |
| High | 74 | `save_usage` is not atomic. Process kill between truncate and write zeroes out monthly spend tracking. | Atomic write via tempfile + `os.replace`. |
| Medium | 199–203 | `iter_content(chunk_size=4096)` writes to `out_mp3` directly while streaming — same partial-download risk as `fetch_trailer.py`. | Stream to `.part`, replace on success. |
| Medium | 185–187 | `with-timestamps` endpoint requires a fully-buffered JSON response (`resp.json()`). On a 60-second narration that can be several MB. Default `requests` reads into memory fine, but the call has no streaming option and no per-chunk progress. Minor. | Document the memory cost; consider falling back to non-aligned for >30 KB scripts if needed. |
| Medium | 186 | `resp.raise_for_status()` on an HTTP error means the BudgetExceeded reservation isn't refunded — but `record_usage` is never called on failure, so we're fine. Confirm in tests. | Add an integration test that simulates an API 500 mid-call and asserts usage didn't increment. |

### scripts/render_video.py (legacy — 403 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| Critical | entire file | **Dead code.** Hardcoded to case `01_gothferrari`. Not referenced by any pipeline (only by `scripts/writer_prompt.md` documentation). `skill/truecrime-short/render_video.py` is the canonical generalized renderer. Leaving this in `scripts/` invites someone to call it accidentally and overwrite scenes/captions for case 01 with stale data. | Delete the file, or move to `archive/`. |
| Low | 350 | `text.replace("'", "'")` is a no-op (left and right sides identical). Stale code. | Delete the line. |

### scripts/upload_to_youtube.py (340 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| Critical | 263–272 | After `request.next_chunk()` returns, the video is *already on YouTube*. If the process is killed between line 263 and the `mark_posted(...)` call on line 271 (e.g., laptop sleeps, network drops, OOM), the video is live but the next `--next` invocation re-discovers it as unposted and uploads a duplicate. The duplicate upload also publishes immediately if no schedule was set. | Write a `_posted.json.uploading` marker the moment the API call begins with the case_id + scheduled time. On success, atomically promote to `_posted.json`. On startup, if a `.uploading` marker exists, look up the channel's recent uploads to detect the duplicate before re-uploading. |
| High | 66–77 | `Credentials.refresh()` with no `try/except RefreshError`. See cross-cutting `OAuth handling`. | Wrap + sys.exit with actionable message. |
| High | 73 | `creds.expired and creds.refresh_token` — but doesn't check `creds.valid`. If the token was just issued but has a clock skew issue, `expired` is False, `valid` is also False, and the upload starts with a bad token. | Use `if not creds.valid: creds.refresh(Request())`. |
| High | 75 | `TOKEN_PATH.write_text(creds.to_json())` — not atomic. A crash here loses the refresh token entirely, locking the channel out until manual re-auth. | Atomic write helper. |
| High | 117 | `save_posted` is not atomic (write_text). See cross-cutting `Atomic writes`. | tempfile + os.replace. |
| Medium | 113 | `json.loads(posted_path.read_text())` raises on a partial/empty file with `json.JSONDecodeError`, which surfaces as an uncaught traceback in cron. | Catch JSONDecodeError, log it, fall back to empty dict but refuse to upload until human reviews — never silently overwrite a corrupt state file. |
| Medium | 158 | `c.startswith(arg + "_") or c.startswith(arg)` — `arg="02"` matches `02_foo` and also `0234_anything`. Resolve order is `c == arg` first, but for `arg="GG_01"` it matches `GG_01_subnautica2` *and* `GG_01_anything_else` → returns the first sorted. | Tighten matching: exact, then `arg+"_"` prefix, never bare prefix. |
| Medium | 250–256 | Retry loop on 5xx has no max-attempts and no delay. A persistent 503 will busy-loop until the upload session expires. | Cap at 5 retries, exponential backoff (1s, 2s, 4s, 8s, 16s). |
| Medium | 196 | `publish_at.isoformat().replace("+00:00", "Z")` — fine in practice, but `isoformat()` can also produce `+0000` without the colon on some Python versions. Use `strftime("%Y-%m-%dT%H:%M:%SZ")`. | Use explicit strftime. |
| Medium | 333 | `args.schedule == "auto"` is the only branch that uses `compute_next_slot()`; passing `--schedule` with no datetime is impossible (argparse requires a value). The auto branch is dead. | Either make `--schedule` `nargs="?"`, or remove the `"auto"` branch and document. |

### scripts/youtube_oauth_setup.py (85 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| High | 78 | `TOKEN_PATH.write_text(creds.to_json())` — same non-atomic write as upload_to_youtube. A crash here is recoverable (just re-run the script) but worth fixing for consistency. | Atomic write. |
| Medium | 56–61 | Interactive `input("Overwrite? [y/N]")` is correct for the manual case but means this script *cannot* be invoked non-interactively. That's actually fine for the use case — call this out in a comment. | Add comment that this script is human-driven, never call from cron. |

Otherwise clean.

### scripts/analyze_performance.py (383 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| High | 63–66 | No `try/except RefreshError`. See cross-cutting. | Wrap. |
| High | 99–105 / 119–126 / 137–145 | Three separate `try/except HttpError` blocks each catch the error and return a dict with `"_error"` — but a 403 (quota exhausted) returns the same structure as a 503 (transient). The report renders both as "Error" without distinction; a daily run during quota exhaustion produces a useless report with no signal that the quota is the issue. | Distinguish 403/quota from transient 5xx; raise on auth (401/403) so the daily cron logs a real problem rather than a silent empty report. |
| Medium | 174–178 | `pub_dt.date().isoformat()` — `pub_dt` is parsed from `info.get("scheduled_publish", "")`, which is the string `"immediate"` for non-scheduled uploads. `datetime.fromisoformat("immediate".replace("Z", "+00:00"))` raises ValueError, caught by the bare `except Exception`. Result: live videos uploaded as immediate-public get a vague "published: immediate" string instead of their actual publish date. | When `scheduled_publish == "immediate"`, fall back to `info.get("uploaded_at")` (which *is* an ISO timestamp). |
| Medium | 75 | `sys.exit` if `_posted.json` doesn't exist — fine, but if `_posted.json` is corrupt (zero bytes from a write_text crash) the script raises JSONDecodeError. | Same as upload_to_youtube — catch + log + refuse rather than crashing. |
| Medium | 327 | `match = [k for k in posted if k == args.case or k.startswith(args.case)]` — same fuzzy prefix issue as resolve_case. | Tighten matching. |

### scripts/quality_loop.py (359 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| Medium | 60–66 | Only loads `timeline_baked.txt` or `timeline.txt` for *truecrime* cases. For game shorts (which have `bg_clips_concat.txt`), the timeline is empty → `find_drop_beat` returns None and no beat-level diagnosis ever fires for game shorts. | Add a `bg_clips_concat.txt` reader, or skip beat mapping for game cases and report only avg view %. |
| Medium | 86–94 | Cumulative duration parsing assumes lines strictly alternate `file ` / `duration `. The concat format from `render_game_video.py:166–190` outputs a doubled `file` line at the end (no duration) — `current_file` gets reset to None after the prior entry, so the duplicate file is skipped. Works today by accident; fragile. | Parse explicitly with a state machine that handles the trailing repeated file. |
| Low | 311–312 | Two of three argparse args (`--threshold`, `--min-views`) are accepted but `args.threshold` is never read. Stale arg. | Remove or wire up. |

### scripts/suggest_improvements.py (224 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| Medium | 205 | `"intel_path" in dir()` — bug. `dir()` returns module-level names, and Python *did* bind `intel_path` in the `try` block, but the linter-style intent (check whether the load succeeded) is unreliable. If the try block raises before binding, `intel_path` may not exist; if it does exist from a prior run, this still returns True. | Track success with an explicit `intel_path: Path | None = None` initialized before the try. |
| Medium | 169–192 | No retry / no timeout on `client.messages.create`. A network blip kills the daily quality loop. | Wrap in a retry helper (3 attempts with backoff). |
| Low | 144 | Reads `writer_prompt.md` from `skill/truecrime-short/` — game shorts use a *different* writer prompt. This script is truecrime-only by design. | Document explicitly at top of file. |

### scripts/research_games.py (384 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| High | 60 / 78 | Bare `except Exception` returns empty list / empty dict. See cross-cutting `except Exception swallows`. | Log the exception type at minimum. |
| High | 196–202 | Claude call with `max_tokens=4000` for up to 20 candidates. If the response truncates, `json.loads` fails and `score_with_claude` returns `[]` → `run_auto` prints "No QUEUED games found" silently. | Detect truncation (`response.stop_reason == "max_tokens"`); chunk the candidates or raise. |
| Medium | 320 | `update_index` uses string `.replace("## How to add", new_rows + "\n\n## How to add")` — if the index has been hand-edited and lacks that section, the rows append at end, *not* in a sorted position. The fallback is correct but the primary path is fragile. | Parse the index as a real document. |
| Medium | 251–254 | `slugify` truncates to 40 chars without ensuring the cut isn't mid-word, and doesn't dedupe — two games named "Half-Life: Alyx" and "Half-Life Alyx Remix" both slugify to `halflife_alyx` and collide on the next queue number lookup. | Append a numeric suffix on collision, or include appid in the slug. |
| Medium | 116 / 117 | `time.sleep(0.3)` between Steam API calls is sequential — 20 candidates × 0.3s = 6s before scoring even starts. Fine, but if Steam rate-limits more aggressively on a daily schedule, no detection or backoff. | Add 429 handling. |

### scripts/research_top_channels.py (255 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| High | 55–65 | No `RefreshError` handling. See cross-cutting. | Wrap. |
| Medium | 65 | `TOKEN_PATH.write_text(creds.to_json())` — not atomic. | Atomic write. |
| Medium | 85–88 | `HttpError` caught and returned as empty list — no distinction between quota-exhausted and transient. A quota-exhausted run produces a "Unique videos analyzed: 0" report which downstream `suggest_improvements.py` happily consumes as if it were a real signal. | Surface quota errors. Also: each search.list costs 100 quota units — 5 queries = 500/day, leaving 9500. Document this. |

### skill/game-short/render_game_video.py (305 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| High | 173 | `file '{clip}'` — if `clip` (a `Path`) contains a single quote (legal on macOS), the concat list breaks. Today's slug regex prevents this, but if a queue file is added by hand without slug normalization, FFmpeg fails with a parse error. | Validate or escape. Use `pathlib.PosixPath` quoting. |
| High | 176–187 | Concat-list "extend last clip" logic appends `duration N` *after* the file, then a duplicate `file` entry, then continues. FFmpeg concat demuxer requires `duration` immediately after the `file` it applies to — the structure produced for the "extra" branch puts `duration` after the *first* `file` entry and *before* the duplicate, which is correct, but the *else* branch on 184 also emits `duration` for the last clip — followed by line 189's *unconditional* `file '{clip}'` repeat. Net effect on the else path: the last clip is listed → duration → listed again → no closing entry. Works because FFmpeg tolerates trailing entries, but the contract is fragile. | Rewrite with explicit cases and a single trailing-file convention. |
| Medium | 95 | Comment says "Title overlay via drawtext requires ... freetype. Skipped here." — the `game_title`/`platform_label`/`show_title` parameters are then unused. Dead args. | Remove the unused params or wire them through ASS. |
| Medium | 233 / 226 | Error messages reference shell commands relative to PROJECT_ROOT but the script's actual cwd when invoked from `game_orchestrator.py:235` is also PROJECT_ROOT — fine, but document. | Comment. |

### skill/truecrime-short/render_video.py (366 lines)

| Severity | Line | Issue | Suggested fix |
|---|---|---|---|
| Medium | 334–338 | `f.unlink()` in a loop with `except PermissionError: pass` — silently ignoring a permission failure means the next ffmpeg invocation may concatenate stale frames mixed with new ones, producing a corrupt video. | Refuse to render if old frames can't be cleared; require manual cleanup. |
| Medium | 274–281 | `subprocess.check_output` for ffprobe — if ffprobe isn't installed, raises `FileNotFoundError` not caught. The orchestrator's outer try/except catches it but the message is a generic "ERROR: [Errno 2] No such file or directory: 'ffprobe'" instead of the helpful "install ffmpeg" message. | Pre-flight check at script start. |
| Medium | 285–296 | `compute_scene_times` divides by `wps` derived from `sum(seg_words)` — if any segment has 0 words (empty `chunks`), wps is unchanged but `seg_speech` for that segment is 0, and the for-loop emits a (start, start+pause) interval. Captions for empty segments get distributed across 0 speech time → divide-by-zero in `per_chunk` on line 346. | Validate every segment has at least 1 chunk and `word_count > 0`. |
| Low | 51 | `COLOR_MAP` uses lowercase keys but case configs in the wild may pass `"Red"` — `.get(c.get("value_color", "white"), WHITE)` silently falls back to white. | `.lower()` the lookup key. |

## Recommended fix order

1. **Atomicity bundle** (1 PR, ~1h): Add `scripts/_atomic.py` with `atomic_write_text`. Apply to `_posted.json`, `elevenlabs_usage.json`, `token.json` (×3), and `mark_queue_status`. **Rationale:** the next overnight cron crash that truncates `_posted.json` re-uploads every video; truncating `token.json` locks out the channel. Highest blast radius, cheapest fix.

2. **Upload idempotency** (`upload_to_youtube.py:208–272`): write `_posted.json.uploading` marker before the API call; promote to `_posted.json` on success; detect orphan marker on startup. **Rationale:** without this, even the most graceful crash mid-upload duplicates a public video.

3. **OAuth refresh error handling** (3 scripts): wrap `creds.refresh()` in try/except → `sys.exit` with re-auth instructions. **Rationale:** the autonomous daily cron will inevitably hit a refresh failure (Google's 7-day "testing" expiry, password change, revoke) and the cryptic crash buries the actionable signal.

4. **`.env` loader hardening** (`make_audio_elevenlabs.py:39–44` → shared helper): strip quotes, ignore inline comments, `setdefault` semantics. **Rationale:** the moment a key with quotes lands in `.env`, every secret-consuming script breaks with an opaque 401.

5. **Partial-file downloads** (`fetch_trailer.py:100`, `make_audio_elevenlabs.py:201`): stream to `.part`, atomic-replace on success. **Rationale:** corrupted half-downloads sit in the cache forever (`step_fetch_trailer` sees the file exists and skips); pipeline silently produces broken clips.

6. **Failure-mode hygiene in orchestrator** (`game_orchestrator.py`): retry counter on queue MD, sentinel `.failed` to invalidate stale outputs, `finally` block ensuring status reset, distinguishing transient network failures from real errors. **Rationale:** prevents the daily cron from busy-looping on a permanently-broken queue entry.

7. **Delete legacy `scripts/render_video.py`** — confirmed unused (only referenced by docs).

8. The remaining Medium findings (subprocess timeout handling, FFmpeg arg escaping, fuzzy-match tightening, log rotation) — apply opportunistically.

## Things NOT flagged (good patterns to preserve)

- `compute_next_slot` is timezone-correct.
- The resumable upload retry loop in `upload_to_youtube.py` (apart from the unbounded retries) uses the right googleapiclient pattern.
- The base-canvas numpy caching in `skill/truecrime-short/render_video.py` is the kind of optimization that's easy to "simplify" into something 10x slower — leave it.
- `make_audio_elevenlabs.py`'s budget gate is the right shape (estimate before call, record after success). Don't refactor it away.
- Use of `cache_control: ephemeral` in `game_script_writer.py` and `suggest_improvements.py` is correct — the writer prompt is large and stable, perfect for caching.
- `argparse` mutually-exclusive groups in `upload_to_youtube.py`, `fetch_trailer.py`, `make_audio_elevenlabs.py`, `select_clips.py`, `game_orchestrator.py` keep the CLI clear.
- Output paths consistently relative to `PROJECT_ROOT` (`Path(__file__).resolve().parent.parent`) — no surprises from cwd.
