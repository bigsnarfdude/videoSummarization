#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from process_video import summarize_transcript

def main():
    if len(sys.argv) < 2:
        print('Usage: python regenerate_summary.py <transcript_path>')
        sys.exit(1)

    transcript_path = Path(sys.argv[1])
    if not transcript_path.exists():
        print(f'Error: {transcript_path} not found')
        sys.exit(1)

    # Read transcript
    with open(transcript_path, 'r') as f:
        transcript_text = f.read()

    # Extract basename for title
    basename = transcript_path.stem

    # Generate summary
    print(f'Summarizing {len(transcript_text.split())} words...')
    summary = summarize_transcript(transcript_text, basename)

    # Save summary
    summary_path = Path('files/summaries') / f'{basename}_summary.txt'
    with open(summary_path, 'w') as f:
        f.write(summary)

    print(f'✅ Summary saved: {summary_path}')
    print(f'Summary length: {len(summary.split())} words')

if __name__ == '__main__':
    main()
