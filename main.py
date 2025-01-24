import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from transcribe.transcribe import transcribe
from transcribe.get_video import process_local_video
from transcribe.summarize_model import split_text, summarize_in_parallel, save_summaries
from transcribe.utils import get_filename
from config import settings

def setup_logging(log_file: str = "transcribe.log") -> None:
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handlers = [
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
    for handler in handlers:
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

def create_logseq_note(summary_path: Path, title: str) -> Optional[Path]:
    if not summary_path.exists():
        raise FileNotFoundError(f"Summary file not found: {summary_path}")

    lines = summary_path.read_text().splitlines()
    if not lines:
        raise ValueError(f"Summary file is empty: {summary_path}")

    logseq_path = settings.OUTPUT_DIRS["logseq"] / f"{summary_path.stem}.md"
    logseq_path.parent.mkdir(parents=True, exist_ok=True)

    with logseq_path.open('w') as f:
        f.write(f"- summarized [[{title}]]\n")
        f.write("- [[summary]]\n")
        f.writelines(f"    {line}\n" for line in lines)

    logging.info(f"✓ Created Logseq note: {logseq_path}")
    return logseq_path

def process_video(input_path: Path, title: str) -> None:
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    logging.info(f"Processing: {input_path}")
    
    # Convert video to audio
    audio_path = process_local_video(str(input_path))
    if not Path(audio_path).exists():
        raise RuntimeError(f"Audio extraction failed: {audio_path}")
    logging.info(f"✓ Created audio: {audio_path}")

    # Transcribe audio
    elapsed_time, transcript, transcript_path = transcribe(audio_path)
    if not Path(transcript_path).exists():
        raise RuntimeError(f"Transcription failed: {transcript_path}")
    logging.info(f"✓ Transcribed in {elapsed_time}s: {transcript_path}")

    # Generate summary
    chunks = split_text(transcript_path, title)
    summaries = summarize_in_parallel(chunks, title)
    summary_path = save_summaries(summaries, get_filename(transcript_path))
    logging.info(f"✓ Created summary: {summary_path}")

    # Create Logseq note
    logseq_path = create_logseq_note(Path(summary_path), title)
    
    logging.info("\nProcessing completed:")
    logging.info(f"  Audio:      {audio_path}")
    logging.info(f"  Transcript: {transcript_path}")
    logging.info(f"  Summary:    {summary_path}")
    logging.info(f"  Logseq:     {logseq_path}")

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Process video files for transcription and summarization.")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to video file")
    parser.add_argument("--title", "-t", type=str, required=True, help="Video title")

    args = parser.parse_args()

    try:
        process_video(Path(args.input), args.title)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()