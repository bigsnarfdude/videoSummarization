#!/bin/bash
# Simplest batch processor - uses JSON for reliable URL handling

LIMIT=${1:-10}

cd ~/videoSummarization
source venv/bin/activate

# Create video list as JSON
python - <<EOPY
import json
import requests
from bs4 import BeautifulSoup
import re
from pathlib import Path

# Load progress
progress_file = Path('data/progress.json')
if progress_file.exists():
    with open(progress_file) as f:
        progress = json.load(f)
else:
    progress = {'processed': [], 'failed': []}

processed_set = set(progress['processed'])

# Scrape videos
workshops_url = 'https://videos.birs.ca/2025/'
resp = requests.get(workshops_url)
soup = BeautifulSoup(resp.text, 'html.parser')

videos = []
for link in soup.find_all('a', href=True):
    match = re.match(r'(\d{2}w\d{4})/', link['href'])
    if match:
        workshop = match.group(1)
        ws_url = f'{workshops_url}{workshop}/'
        ws_resp = requests.get(ws_url)
        ws_soup = BeautifulSoup(ws_resp.text, 'html.parser')

        for vid_link in ws_soup.find_all('a', href=True):
            if vid_link['href'].endswith('.mp4'):
                vmatch = re.match(r'(\d{12})-(.+)\.mp4', vid_link['href'])
                if vmatch:
                    timestamp, speaker = vmatch.groups()
                    basename = f'{workshop}_{timestamp}_{speaker}'
                    if basename not in processed_set:
                        videos.append({
                            'url': f'{ws_url}{vid_link["href"]}',
                            'basename': basename
                        })

# Save as JSON
with open('/tmp/videos.json', 'w') as f:
    json.dump(videos[:$LIMIT], f, indent=2)

print(f'Found {len(videos)} unprocessed videos')
print(f'Processing first {min(len(videos), $LIMIT)}')
EOPY

# Get total count
total=$(python -c "import json; print(len(json.load(open('/tmp/videos.json'))))")

echo ""
echo "Processing $total videos..."

# Process each video
for i in $(seq 0 $((total - 1))); do
    # Extract video info from JSON
    VIDEO_DATA=$(python -c "import json; v = json.load(open('/tmp/videos.json'))[$i]; print(v['url']); print(v['basename'])")
    url=$(echo "$VIDEO_DATA" | head -1)
    basename=$(echo "$VIDEO_DATA" | tail -1)

    echo ""
    echo "=========================================="
    echo "[$((i+1))/$total] $basename"
    echo "=========================================="

    # Kill Python and wait for GPU to clear
    pkill -9 python 2>/dev/null || true
    sleep 3

    # Process video
    python process_video.py "$url" "$basename"
    status=$?

    # Update progress
    if [ $status -eq 0 ]; then
        python -c "import json; from pathlib import Path; p = Path('data/progress.json'); d = json.load(open(p)) if p.exists() else {'processed': [], 'failed': []}; d['processed'].append('$basename'); json.dump(d, open(p, 'w'), indent=2)"
        echo "✅ Success"
    else
        python -c "import json; from pathlib import Path; p = Path('data/progress.json'); d = json.load(open(p)) if p.exists() else {'processed': [], 'failed': []}; d['failed'].append({'basename': '$basename', 'error': 'Failed'}); json.dump(d, open(p, 'w'), indent=2)"
        echo "❌ Failed"
    fi
done

echo ""
echo "=========================================="
echo "COMPLETE"
echo "=========================================="
python -c "import json; p = json.load(open('data/progress.json')); print(f\"Processed: {len(p['processed'])}\"); print(f\"Failed: {len(p['failed'])}\")"
