# BIRS Video Processing System for Nigel

## Overview

Automated system for processing BIRS video lectures from videos.birs.ca:
- **Scrapes** videos.birs.ca/2025/ and /2026/ for new videos
- **Transcribes** using NVIDIA Parakeet TDT (blazing fast!)
- **Summarizes** using gpt-oss:20b (local Ollama)
- **Stores** MP3 for future audio.birs.ca site

---

## Security Model: SSH-Only Access

✅ **Flask runs on localhost:5000 only** (no external access)
✅ **SSH tunnel required** for web UI
✅ **CLI tools** for all operations
✅ **No public API** endpoints

---

## Quick Deploy

From your Mac:

```bash
cd /Users/vincent/nigel/videoProcessing/videoSummarization
./deploy.sh
```

This will:
1. Copy files to nigel
2. Set up Python virtual environment
3. Install dependencies (including Parakeet + Ollama)
4. Initialize database
5. Create directories

Takes ~10 minutes for first deployment.

---

## Usage on Nigel

### SSH to Nigel

```bash
ssh nigel
cd ~/videoSummarization
source venv/bin/activate
```

### 1. Discover New Videos

```bash
python cli/birs-cli.py scrape
```

This will:
- Scrape videos.birs.ca/2025/ and /2026/
- Add new videos to database
- Show stats (pending, complete, failed)

### 2. Check Status

```bash
python cli/birs-cli.py status
```

Shows:
- Total videos discovered
- Pending queue
- Currently processing
- Completed
- Failed

### 3. Process Videos

**Test with one video:**
```bash
python cli/birs-cli.py process --once --batch-size 1
```

**Process batch:**
```bash
python cli/birs-cli.py process --once --batch-size 10
```

**Run continuous worker:**
```bash
python worker.py
```

(Press Ctrl+C to stop)

### 4. View Recent Videos

```bash
python cli/birs-cli.py recent --limit 20
```

### 5. Reset Failed Videos

If some videos failed (network issue, etc.):

```bash
python cli/birs-cli.py reset-failed
```

---

## Web UI Access (Optional)

Flask runs on **localhost:5000 only** (not accessible externally).

### Access via SSH Tunnel

From your Mac:

```bash
ssh -L 5000:localhost:5000 nigel
```

Then open: **http://localhost:5000**

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│  Scraper (hourly cron)                               │
│  - Scans videos.birs.ca/2025/, /2026/               │
│  - Adds new videos to database                       │
└───────────────────┬─────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  Queue (SQLite database)                             │
│  - Pending videos                                    │
│  - Processing status                                 │
│  - Complete/failed tracking                          │
└───────────────────┬─────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  Worker (background process)                         │
│  1. Download video from videos.birs.ca              │
│  2. Extract audio (WAV + MP3)                        │
│  3. Transcribe with Parakeet TDT (~5sec!)           │
│  4. Summarize with gpt-oss:20b (~5min)              │
│  5. Save artifacts, cleanup                          │
└───────────────────┬─────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  Artifacts (stored locally)                          │
│  ✅ MP3 audio (18MB) - keep for audio.birs.ca       │
│  ✅ Transcript (50KB) - keep for search             │
│  ✅ Summary (10KB) - keep for quick read            │
│  ❌ Video (62MB) - delete after processing          │
│  ❌ WAV (180MB) - delete after transcription        │
└─────────────────────────────────────────────────────┘
```

---

## Processing Speed

**30-minute lecture:**
- Download: ~1-2 min
- Audio extraction: ~30 sec
- Transcription: **~5 sec** (Parakeet is FAST!)
- Summarization: ~5 min
- **Total: ~7-8 minutes**

**Batch processing:**
- 10 videos/hour = ~70-80 min processing time
- 500 videos (full 2025 archive) = ~2 days at 10/hour

---

## Storage

**Per video:**
- MP3 audio: ~18MB
- Transcript: ~50KB
- Summary: ~10KB
- **Total: ~18MB**

**Full 2025 archive (500 videos):**
- **~9GB total** (very manageable!)

Temporary files (video, WAV) are deleted after processing.

---

## File Naming Convention

Follows videos.birs.ca pattern:

```
Video URL:
https://videos.birs.ca/2025/25w5331/202506050900-Montejano.mp4

Generated files:
files/audio/mp3/25w5331_202506050900_Montejano.mp3
files/transcripts/25w5331_202506050900_Montejano.txt
files/summaries/25w5331_202506050900_Montejano_summary.txt
```

Pattern: `{workshop}_{timestamp}_{speaker}.{ext}`

---

## Database Schema

SQLite database at `data/archive.db`:

```sql
CREATE TABLE videos (
    id TEXT PRIMARY KEY,
    source TEXT,          -- 'archive' or 'manual'
    video_url TEXT UNIQUE,
    workshop_id TEXT,
    speaker TEXT,
    timestamp TEXT,
    status TEXT,          -- 'pending', 'processing', 'complete', 'failed'
    transcript_path TEXT,
    summary_path TEXT,
    mp3_path TEXT,        -- For audio.birs.ca
    error_message TEXT,
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

---

## CLI Commands Reference

```bash
# Discover new videos
python cli/birs-cli.py scrape

# Check queue status
python cli/birs-cli.py status

# Process one batch (test)
python cli/birs-cli.py process --once

# Process with custom batch size
python cli/birs-cli.py process --once --batch-size 5

# Start continuous worker
python cli/birs-cli.py process

# View recent videos
python cli/birs-cli.py recent --limit 20

# Reset failed videos to pending
python cli/birs-cli.py reset-failed
```

---

## Automation Setup (Optional)

### Cron Job for Hourly Scraping

Edit crontab on nigel:

```bash
crontab -e
```

Add:

```cron
# Scrape for new videos every hour
0 * * * * cd ~/videoSummarization && source venv/bin/activate && python cli/birs-cli.py scrape >> logs/scraper.log 2>&1
```

### Systemd Service for Worker (Recommended)

Create `/etc/systemd/system/birs-worker.service`:

```ini
[Unit]
Description=BIRS Video Processing Worker
After=network.target

[Service]
Type=simple
User=vincent
WorkingDirectory=/home/vincent/videoSummarization
ExecStart=/home/vincent/videoSummarization/venv/bin/python worker.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable birs-worker
sudo systemctl start birs-worker

# Check status
sudo systemctl status birs-worker

# View logs
sudo journalctl -u birs-worker -f
```

---

## Troubleshooting

### "Import error: nemo_toolkit"

```bash
pip install nemo_toolkit[asr]
```

### "CUDA out of memory"

Reduce batch size:

```bash
python cli/birs-cli.py process --once --batch-size 1
```

### "Ollama connection refused"

Check Ollama is running:

```bash
ollama list
curl http://localhost:11434/api/generate -d '{"model":"gpt-oss:20b","prompt":"test"}'
```

### "Videos not being discovered"

Check scraper:

```bash
python scraper/birs_archive_scraper.py
```

### View logs

```bash
tail -f logs/app.log
```

---

## Phase 2: audio.birs.ca (Future)

When ready to deploy audio files publicly:

### 1. Transfer MP3s to videos.birs.ca server

```bash
# From nigel
rsync -avz --progress \
  ~/videoSummarization/files/audio/mp3/ \
  videos.birs.ca:/var/www/audio.birs.ca/public_html/
```

### 2. Apache VirtualHost

Add to Apache config on videos.birs.ca:

```apache
<VirtualHost *:80>
    ServerName audio.birs.ca
    DocumentRoot /var/www/audio.birs.ca/public_html

    <Directory /var/www/audio.birs.ca/public_html>
        Options +Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
        AddType audio/mpeg .mp3
        Header set Accept-Ranges bytes
    </Directory>
</VirtualHost>
```

### 3. URL Structure

Mirrors videos.birs.ca:

```
https://videos.birs.ca/2025/25w5331/202506050900-Montejano.mp4
https://audio.birs.ca/2025/25w5331/202506050900-Montejano.mp3
```

---

## Performance on Nigel

**Hardware:**
- GPU: NVIDIA RTX 4070 Ti Super (16GB VRAM)
- Ollama: gpt-oss:20b (13GB model)
- Parakeet TDT: 0.6B (2-4GB VRAM)

**Expected Performance:**
- Transcription: 3386x faster than realtime (1hr video → ~1sec)
- Summarization: ~50-100 tokens/sec
- Can run both simultaneously (plenty of VRAM)

**Throughput:**
- ~10 videos/hour (7-8 min each)
- ~240 videos/day
- Full 2025 archive (500 videos) → ~2 days

---

## Support

Questions or issues:
- Check logs: `tail -f logs/app.log`
- View database: `sqlite3 data/archive.db`
- CLI help: `python cli/birs-cli.py --help`

---

## Summary

✅ **Security**: localhost-only, SSH tunnel access
✅ **Fast**: Parakeet TDT transcription (~5sec for 30min)
✅ **Efficient**: 18MB storage per video
✅ **Automated**: Scraper + worker handles everything
✅ **MP3 ready**: Files ready for future audio.birs.ca
✅ **Local**: No API costs, fully offline processing

Ready to process the entire BIRS 2025/2026 archive!
