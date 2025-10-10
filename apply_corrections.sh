#!/bin/bash
# Apply transcript corrections and regenerate summaries
set -e

cd ~/videoSummarization
source venv/bin/activate

echo "=========================================="
echo "Applying Transcript Corrections"
echo "=========================================="

# List of transcripts needing correction
TRANSCRIPTS=(
    "files/transcripts/25w5318_202507210900_Walton.txt"
    "files/transcripts/25w2030_202505030902_Hamieh.txt"
)

for transcript in "${TRANSCRIPTS[@]}"; do
    echo ""
    echo "Processing: $transcript"

    basename=$(basename "$transcript" .txt)
    corrected="${transcript%.txt}_corrected.txt"
    summary="files/summaries/${basename}_summary.txt"

    # Check if corrected version exists
    if [ ! -f "$corrected" ]; then
        echo "⚠️  Corrected version not found, skipping"
        continue
    fi

    # Backup original
    echo "  1. Backing up original..."
    cp "$transcript" "${transcript}.backup"

    # Replace with corrected
    echo "  2. Applying corrections..."
    mv "$corrected" "$transcript"

    # Backup old summary
    if [ -f "$summary" ]; then
        echo "  3. Backing up old summary..."
        cp "$summary" "${summary}.backup"
    fi

    # Regenerate summary
    echo "  4. Regenerating summary..."
    python - <<EOF
import sys
sys.path.insert(0, '.')
from process_video import summarize_transcript

# Read corrected transcript
with open('$transcript', 'r') as f:
    transcript_text = f.read()

# Extract basename for title
title = '$basename'

print(f"Summarizing {len(transcript_text.split())} words...")
summary = summarize_transcript(transcript_text, title)

# Save new summary
with open('$summary', 'w') as f:
    f.write(summary)

print(f"✅ New summary: {len(summary.split())} words")
EOF

    echo "  ✅ Complete!"
done

echo ""
echo "=========================================="
echo "Correction Summary"
echo "=========================================="
echo "Fixed transcripts: ${#TRANSCRIPTS[@]}"
echo ""
echo "To compare before/after:"
echo "  diff files/transcripts/25w5318_202507210900_Walton.txt.backup files/transcripts/25w5318_202507210900_Walton.txt"
echo ""
echo "Backups saved with .backup extension"
