#!/bin/bash
# Simple batch processor - runs videos one at a time with GPU cleanup

LIMIT=${1:-3}  # Default: process 3 videos

cd ~/videoSummarization
source venv/bin/activate

# Get list of unprocessed videos
python -c "
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

# Quick scrape 2025 videos
workshops_url = 'https://videos.birs.ca/2025/'
resp = requests.get(workshops_url)
soup = BeautifulSoup(resp.text, 'html.parser')

videos = []
for link in soup.find_all('a', href=True):
    match = re.match(r'(\d{2}w\d{4})/', link['href'])
    if match:
        workshop = match.group(1)
        # Get videos from this workshop
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
                        videos.append(f'{ws_url}{vid_link[\"href\"]}|||{basename}')

# Save to file
with open('/tmp/video_list.txt', 'w') as f:
    for v in videos[:$LIMIT]:
        f.write(v + '\n')

print(f'Found {len(videos)} unprocessed videos')
print(f'Processing first {min(len(videos), $LIMIT)}')
"

# Process each video
total=$(wc -l < /tmp/video_list.txt)
current=1

while IFS='|||' read -r url basename; do
    # Parse with delimiter to handle URL properly

    echo ""
    echo "=========================================="
    echo "[$current/$total] $basename"
    echo "=========================================="

    # Kill any stuck Python processes and clear GPU
    pkill -9 python 2>/dev/null || true
    sleep 2

    # Force clear GPU if needed
    nvidia-smi --gpu-reset 2>/dev/null || true
    sleep 1

    # Process this video
    python process_video.py "$url" "$basename"

    # Update progress
    if [ $? -eq 0 ]; then
        python -c "
import json
from pathlib import Path
p = Path('data/progress.json')
data = json.load(open(p)) if p.exists() else {'processed': [], 'failed': []}
data['processed'].append('$basename')
json.dump(data, open(p, 'w'), indent=2)
"
        echo "✅ Success"
    else
        python -c "
import json
from pathlib import Path
p = Path('data/progress.json')
data = json.load(open(p)) if p.exists() else {'processed': [], 'failed': []}
data['failed'].append({'basename': '$basename', 'error': 'Failed'})
json.dump(data, open(p, 'w'), indent=2)
"
        echo "❌ Failed"
    fi

    current=$((current + 1))
done < /tmp/video_list.txt

echo ""
echo "=========================================="
echo "COMPLETE"
echo "=========================================="
python -c "
import json
p = json.load(open('data/progress.json'))
print(f\"Processed: {len(p['processed'])}\")
print(f\"Failed: {len(p['failed'])}\")
"
