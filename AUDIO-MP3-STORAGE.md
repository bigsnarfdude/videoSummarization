# Audio MP3 Storage Strategy

## Future Goal: audio.birs.ca
- **Phase 2**: Create audio.birs.ca site on Apache (videos.birs.ca server)
- **Purpose**: Stream/download audio-only versions of lectures
- **Format**: MP3 (compressed, web-friendly)
- **For Now**: Keep all MP3 files locally for later upload

---

## Updated Processing Pipeline

### Step 3: Extract Audio (UPDATED)

**Old workflow** (delete audio after):
```bash
Video → WAV (16kHz mono) → Transcribe → Delete WAV
```

**New workflow** (keep MP3 for audio.birs.ca):
```bash
Video → WAV (16kHz mono) → Transcribe
      ↓
      └─→ MP3 (128kbps stereo) → ✅ KEEP for audio.birs.ca
```

### Code Changes

```python
# transcribe/get_video.py - UPDATED

def extract_audio(video_path, output_dir="files/audio"):
    """Extract audio in TWO formats:
    1. WAV (16kHz mono) - for transcription
    2. MP3 (128kbps) - for audio.birs.ca
    """
    from pathlib import Path
    import subprocess

    video_file = Path(video_path)
    basename = video_file.stem  # e.g., "25w5331_202506050900_Montejano"

    # Create subdirectories
    wav_dir = Path(output_dir) / "wav"
    mp3_dir = Path(output_dir) / "mp3"
    wav_dir.mkdir(parents=True, exist_ok=True)
    mp3_dir.mkdir(parents=True, exist_ok=True)

    wav_path = wav_dir / f"{basename}.wav"
    mp3_path = mp3_dir / f"{basename}.mp3"

    # Extract WAV for transcription (16kHz mono)
    subprocess.run([
        'ffmpeg', '-i', str(video_path),
        '-ar', '16000',  # 16kHz sample rate (Parakeet requirement)
        '-ac', '1',      # Mono
        '-c:a', 'pcm_s16le',  # WAV format
        str(wav_path)
    ], check=True)

    # Extract MP3 for audio.birs.ca (128kbps stereo)
    subprocess.run([
        'ffmpeg', '-i', str(video_path),
        '-b:a', '128k',  # 128kbps bitrate
        '-ac', '2',      # Stereo
        '-ar', '44100',  # Standard audio sample rate
        str(mp3_path)
    ], check=True)

    return {
        'wav': str(wav_path),  # For transcription
        'mp3': str(mp3_path)   # For audio.birs.ca
    }
```

---

## Storage Changes

### Old Approach (Delete Everything)
```
files/
├── downloads/
│   └── video.mp4              (62MB) → DELETE after processing
└── audio/
    └── audio.wav              (180MB) → DELETE after transcription

Total kept: 60KB (transcript + summary)
```

### New Approach (Keep MP3)
```
files/
├── downloads/
│   └── video.mp4              (62MB) → DELETE after processing
├── audio/
│   ├── wav/
│   │   └── audio.wav          (180MB) → DELETE after transcription
│   └── mp3/
│       └── audio.mp3          (18MB) ✅ KEEP for audio.birs.ca
├── transcripts/
│   └── transcript.txt         (50KB) ✅ KEEP
└── summaries/
    └── summary.txt            (10KB) ✅ KEEP

Total kept per video: ~18MB
```

### Storage Requirements

**Per video (30min lecture):**
- MP3 (128kbps): ~18MB
- Transcript: ~50KB
- Summary: ~10KB
- **Total: ~18MB per video**

**Full 2025 archive (estimated 500 videos):**
- 500 videos × 18MB = **~9GB storage**

**This is totally manageable on nigel!**

---

## File Naming Convention

Follow existing pattern from videos.birs.ca:

```
Video URL:
https://videos.birs.ca/2025/25w5331/202506050900-Montejano.mp4

Generated files:
files/audio/mp3/25w5331_202506050900_Montejano.mp3         (audio.birs.ca)
files/transcripts/25w5331_202506050900_Montejano.txt       (text search)
files/summaries/25w5331_202506050900_Montejano_summary.txt (quick read)
```

Pattern: `{workshop}_{timestamp}_{speaker}.{ext}`

---

## Database Schema Update

Add `mp3_path` field:

```sql
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    source TEXT,
    video_url TEXT UNIQUE,
    workshop_id TEXT,
    speaker TEXT,
    timestamp TEXT,
    status TEXT,
    transcript_path TEXT,
    summary_path TEXT,
    mp3_path TEXT,          -- NEW: Path to MP3 for audio.birs.ca
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);
```

---

## Worker Processing Update

```python
# worker.py - Updated processing flow

def process_video_task(task):
    """Process a single video from queue"""

    # 1. Download video
    video_path = download_video(task.video_url)

    # 2. Extract audio (WAV + MP3)
    audio_files = extract_audio(video_path)
    # Returns: {'wav': 'files/audio/wav/...', 'mp3': 'files/audio/mp3/...'}

    # 3. Transcribe using WAV
    transcript_path = transcribe_audio(audio_files['wav'])

    # 4. Summarize transcript
    summary_path = summarize_transcript(transcript_path)

    # 5. Save MP3 path to database
    db.update_task(task.task_id, {
        'transcript_path': transcript_path,
        'summary_path': summary_path,
        'mp3_path': audio_files['mp3'],  # ✅ Keep MP3 reference
        'status': 'complete'
    })

    # 6. Cleanup temporary files
    os.remove(video_path)           # Delete original video (62MB)
    os.remove(audio_files['wav'])   # Delete WAV (180MB)
    # ✅ KEEP audio_files['mp3']     # Keep MP3 (18MB)
```

---

## Future Phase 2: audio.birs.ca Deployment

### On videos.birs.ca Apache Server

**Step 1: Create directory structure**
```bash
ssh videos.birs.ca
sudo mkdir -p /var/www/audio.birs.ca/public_html
sudo chown www-data:www-data /var/www/audio.birs.ca/public_html
```

**Step 2: Transfer MP3 files from nigel**
```bash
# From nigel
rsync -avz --progress \
  ~/videoSummarization/files/audio/mp3/ \
  videos.birs.ca:/var/www/audio.birs.ca/public_html/
```

**Step 3: Apache VirtualHost**
```apache
<VirtualHost *:80>
    ServerName audio.birs.ca
    DocumentRoot /var/www/audio.birs.ca/public_html

    <Directory /var/www/audio.birs.ca/public_html>
        Options +Indexes +FollowSymLinks
        AllowOverride None
        Require all granted

        # Enable audio streaming
        AddType audio/mpeg .mp3
        Header set Accept-Ranges bytes
    </Directory>

    # Enable compression for better streaming
    <IfModule mod_deflate.c>
        AddOutputFilterByType DEFLATE audio/mpeg
    </IfModule>
</VirtualHost>
```

**Step 4: Structure matches videos.birs.ca**
```
https://videos.birs.ca/2025/25w5331/202506050900-Montejano.mp4
https://audio.birs.ca/2025/25w5331/202506050900-Montejano.mp3
                        ^-- Same path structure
```

---

## Automated Sync to audio.birs.ca (Future)

**Option 1: Cron job on nigel**
```bash
# /etc/cron.daily/sync-audio-birs

#!/bin/bash
# Sync new MP3s to audio.birs.ca daily

rsync -avz --progress \
  --include='*/' \
  --include='*.mp3' \
  --exclude='*' \
  ~/videoSummarization/files/audio/mp3/ \
  videos.birs.ca:/var/www/audio.birs.ca/public_html/

# Only uploads NEW/CHANGED files (efficient)
```

**Option 2: Trigger after each video**
```python
# worker.py - after successful processing

if task_complete:
    # Upload MP3 to audio.birs.ca immediately
    subprocess.run([
        'scp',
        audio_files['mp3'],
        f'videos.birs.ca:/var/www/audio.birs.ca/public_html/{workshop_id}/'
    ])
```

---

## Benefits of MP3 Storage

✅ **Accessibility**: Audio-only option for users with bandwidth constraints
✅ **Download Speed**: 18MB vs 62MB (3× faster)
✅ **Mobile-Friendly**: Easier to stream on phones
✅ **Podcast-like**: Can listen while commuting
✅ **Searchable**: Combined with transcripts for audio search
✅ **Archive Completeness**: Video + Audio + Transcript + Summary

---

## Implementation Order

**Phase 1: Now (Local Processing)**
1. ✅ Extract MP3 during processing
2. ✅ Store MP3 in files/audio/mp3/
3. ✅ Save mp3_path to database
4. ✅ Keep MP3s on nigel (~9GB for 500 videos)

**Phase 2: Later (Public Deployment)**
1. Set up audio.birs.ca Apache VirtualHost
2. Transfer MP3 files to audio.birs.ca
3. Test streaming
4. Automate sync (cron or per-video)
5. Update BIRS website to link to audio versions

---

## Storage Summary

### What We Keep (per video):
- ✅ MP3 audio: ~18MB (audio.birs.ca)
- ✅ Transcript: ~50KB (text search)
- ✅ Summary: ~10KB (quick overview)
- **Total: ~18MB per video**

### What We Delete (temporary):
- ❌ Original video: 62MB (already at videos.birs.ca)
- ❌ WAV audio: 180MB (only for transcription)

### Total Storage (500 videos):
- **9GB** - Completely manageable on nigel!

---

## Questions Answered

> "we need to keep audio for mp3 processing to audio.birs.ca"
✅ MP3 files kept in files/audio/mp3/

> "that we will have to create on videos.birs.ca apache in last phase"
✅ Phase 2 plan documented above

> "for now keep all the mp3 for later"
✅ Storage strategy: keep MP3, delete video/WAV

---

Ready to implement with MP3 storage! Should I update the code now?
