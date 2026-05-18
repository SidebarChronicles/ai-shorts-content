# YouTube Upload — One-time Setup

Get the `/upload-next-video` and `/upload-case` slash commands working in Claude Code. After this, every upload is one command.

**Time budget:** about 15 minutes the first time. Zero thereafter.

---

## What you'll have at the end

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
claude
> /upload-next-video
```

Claude finds the next unposted mp4, uploads it via YouTube Data API v3, sets the AI synthetic-content disclosure flag, schedules it as private→public at the next 6 PM local time (at least 24h out), and reports back the video_id + watch URL.

---

## Step 1 — Google Cloud project (5 min)

1. Open <https://console.cloud.google.com> in any browser.
2. Top bar → project dropdown → **New Project**.
   - Name: `truecrime-shorts-uploader` (or whatever).
   - Click **Create**.
3. After creation, make sure that project is selected in the top bar.

## Step 2 — Enable the YouTube Data API (1 min)

1. In the left sidebar: **APIs & Services → Library**.
2. Search for `YouTube Data API v3`.
3. Click it → **Enable**.

## Step 3 — Configure the OAuth consent screen (3 min)

1. **APIs & Services → OAuth consent screen**.
2. User type: **External** → Create.
3. App information:
   - App name: `TrueCrime Shorts Uploader` (or anything; only you see it).
   - User support email: your address.
   - Developer contact: your address.
   - Leave everything else blank.
4. **Save and continue** → **Save and continue** (skip scopes) → on the Test users page, **+ ADD USERS** → enter the Google account that owns the YouTube channel → **Save and continue** → **Back to dashboard**.

Note: The app stays in "Testing" mode forever for personal use. No verification needed. You just have to be listed as a test user.

## Step 4 — Create OAuth credentials (2 min)

1. **APIs & Services → Credentials → + Create Credentials → OAuth client ID**.
2. Application type: **Desktop app**.
3. Name: `truecrime-uploader-desktop`.
4. Click **Create**.
5. In the success dialog, click **DOWNLOAD JSON**.
6. Save the downloaded file as `client_secret.json` in the project root (same folder as `SPEC.md`).

## Step 5 — Install Python deps (1 min)

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
python3 -m venv .venv-upload
source .venv-upload/bin/activate
pip install -r scripts/requirements_upload.txt
```

### Step 5b — Install the slash commands (10 sec)

```bash
bash scripts/install_claude_commands.sh
```

This symlinks the upload-* slash command files into `.claude/commands/` so Claude Code can discover them. (Cowork doesn't have write access to `.claude/`, which is why this is a separate step you run locally.)

## Step 6 — Run the one-time OAuth flow (1 min)

```bash
python scripts/youtube_oauth_setup.py
```

A browser tab opens.

- Sign in with the Google account that owns the channel.
- You'll see a warning: "Google hasn't verified this app." That's expected — the app is in personal Testing mode. Click **Continue** → **Advanced** → **Go to TrueCrime Shorts Uploader (unsafe)**.
- Click **Allow** to grant the upload permission.
- Browser tab will say "OAuth complete."

A `token.json` file now exists in the project root. **Don't commit it.** A `.gitignore` entry is included.

## Step 7 — Verify

```bash
python scripts/upload_to_youtube.py --list
```

You should see:

```
  [READY ] 01_gothferrari
  [READY ] 02_ransomware_negotiator
  [READY ] 03_fugitive_crypto_scam
  [READY ] 04_cargo_heist
  [READY ] 05_nfl_medicare_fraud
  [READY ] 06_genetic_testing_fraud
```

(If you've already manually uploaded `01_gothferrari` via Studio, you can mark it posted by hand in `output/videos/_posted.json` — see template below.)

## Step 8 — Dry run before the real one

```bash
python scripts/upload_to_youtube.py --case 02 --dry-run
```

This prints the upload plan (title, tags, scheduled time, AI disclosure flag) without actually uploading. Make sure the title and description look right.

## Step 9 — Real upload

```bash
python scripts/upload_to_youtube.py --case 02
```

It uploads, prints progress (% complete), and prints the watch URL.

Open YouTube Studio → Content → you'll see the video as **Scheduled** until the publish timestamp passes. At that timestamp it flips to Public automatically.

---

## Day-to-day use

Inside the project folder, open Claude Code:

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
claude
```

Then any of:

| Slash command | Action |
|---|---|
| `/upload-next-video` | Upload the next case from the queue |
| `/upload-case 03` | Upload case #03 specifically |
| `/upload-case 04_cargo_heist` | Same, by full case_id |
| `/upload-list` | Show posted/ready status of every case |

The slash commands live in `.claude/commands/` and shell out to `scripts/upload_to_youtube.py`. You can run the script directly too — slash commands are just nicer ergonomics.

---

## Quota math

- YouTube Data API v3 default quota: **10,000 units/day**
- One video upload: **1,600 units**
- So you can upload **6 videos/day** on the default quota
- We're shipping 1/day for the first 60 days — well within budget

If you ever want to scale past 6/day, you can apply for a quota increase in Google Cloud Console (free, takes a few days).

---

## Manually marking case 01 as posted (if you uploaded it via Studio)

Create or edit `output/videos/_posted.json`:

```json
{
  "01_gothferrari": {
    "video_id": "REPLACE_WITH_YOUR_VIDEO_ID",
    "uploaded_at": "2026-05-17T20:00:00+00:00",
    "scheduled_publish": "2026-05-17T22:00:00+00:00",
    "watch_url": "https://www.youtube.com/watch?v=REPLACE_WITH_YOUR_VIDEO_ID"
  }
}
```

Get the video_id from the YouTube Studio URL after you uploaded — it's the string after `v=` in the watch URL.

After that, `/upload-next-video` will skip case 01 and start with case 02.

---

## Troubleshooting

**"Google hasn't verified this app" warning during OAuth**
Expected. The app is in personal Testing mode forever — you just click through. As long as you're listed as a test user (Step 3), it works indefinitely.

**`HttpError 403 quotaExceeded`**
You've used >10,000 units today. Wait until 12:00 AM Pacific (Google's quota reset). Or apply for a quota increase.

**`HttpError 401 invalid_grant`**
The OAuth refresh token was revoked or has expired (Google rotates tokens after long inactivity). Re-run `python scripts/youtube_oauth_setup.py` — same browser flow, takes 30 seconds.

**`HttpError 403 youtubeSignupRequired`**
The Google account isn't linked to a YouTube channel. Open <https://youtube.com>, create the channel, retry.

**Video uploads but doesn't appear scheduled**
Check that the publish time you supplied is in the future. Anything ≤ now becomes immediately public.

**Want to change the daily publish time from 6 PM**
Either pass `--publish-at "2026-05-20T15:00:00"` per upload, or edit the default in `scripts/upload_to_youtube.py` (`compute_next_slot(hour_local=...)`).

---

## What lives where

```
project root/
├── client_secret.json      ← from Google Cloud (do not commit)
├── token.json              ← from OAuth flow (do not commit)
├── .venv-upload/           ← Python venv for the uploader
├── scripts/
│   ├── upload_to_youtube.py
│   ├── youtube_oauth_setup.py
│   └── requirements_upload.txt
├── .claude/commands/             ← symlinks created by install_claude_commands.sh
│   ├── upload-next-video.md      ↳ scripts/claude_commands/upload-next-video.md
│   ├── upload-case.md            ↳ scripts/claude_commands/upload-case.md
│   └── upload-list.md            ↳ scripts/claude_commands/upload-list.md
├── scripts/claude_commands/      ← source-of-truth for the slash command files
│   ├── upload-next-video.md
│   ├── upload-case.md
│   └── upload-list.md
└── output/videos/
    ├── _posted.json        ← uploader tracks state here
    ├── 01_gothferrari.mp4
    ├── 01_gothferrari.description.md
    ├── 02_ransomware_negotiator.mp4
    └── … etc
```
