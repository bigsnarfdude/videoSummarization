import argparse
import os
import sys
import logging
from transcribe.summarize_model import save_summaries, split_text, summarize_in_parallel
from transcribe.transcribe import transcribe
from transcribe.get_video import convert_to_wav, process_local_video
from transcribe.utils import get_filename

# Constants
LOG_FILE = "transcribe.log"
SUMMARIES_DIR = "files/summaries"
LOGSEQ_DIR = "files/logseq"

# Configure logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def create_logseq_note(summary_path, title):
    """Creates a Logseq note from a summary file.

    Args:
        summary_path: Path to the summary file.
        title: Title of the video/source.

    Returns:
        The path to the created Logseq note, or None on error.
    """
    try:
        with open(summary_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logging.error(f"Summary file not found: {summary_path}")
        return None

    formatted_lines = ["    " + line for line in lines]

    summary_filename = os.path.basename(summary_path)
    logseq_filename = os.path.splitext(summary_filename)[0] + ".md"  # More robust
    logseq_note_path = os.path.join(LOGSEQ_DIR, logseq_filename)
    os.makedirs(os.path.dirname(logseq_note_path), exist_ok=True)

    try:
        with open(logseq_note_path, "w") as f:
            f.write(f"- summarized [[{title}]]\n")
            f.write("- [[summary]]\n")
            f.writelines(formatted_lines)
        logging.info(f"Logseq note saved at {logseq_note_path}")
        return logseq_note_path
    except IOError as e:
        logging.error(f"Error writing Logseq note: {e}")
        return None

def call_mlx_model(text_path, title):
    """Summarizes text using the MLX model.

    Args:
        text_path: Path to the text file.
        title: Title of the source.

    Returns:
        The path to the saved summary file, or None on error.
    """
    filename_only = get_filename(text_path)

    try:
        chunks = split_text(text_path=text_path, title=title)
        logging.info(f"Found {len(chunks)} chunks. Summarizing using MLX model...")

        summaries = summarize_in_parallel(chunks)
        summary_path = save_summaries(summaries, filename_only)
        logging.info(f"Summary saved at {summary_path}.")
        return summary_path
    except Exception as e: # Catching a broader exception here to avoid unexpected crashes from the model
        logging.error(f"Error during MLX model processing: {e}")
        return None

def process_local(input_path, title):
    """Processes a local video file.

    Args:
        input_path: Path to the video file.
        title: Title of the video.
    """

    if not os.path.isfile(input_path):
        logging.error(f"Input file not found: {input_path}")
        return

    logging.info(f"Processing local video file: {input_path}")
    try:
        audio_path = process_local_video(input_path)
        logging.info(f"Audio extracted to: {audio_path}")

        logging.info(f"Transcribing {audio_path} (this may take a while)...")
        elapsed_time, transcript_path = transcribe(audio_path)
        logging.info(f"Audio has been transcribed in {int(elapsed_time)} seconds")

        summary_path = call_mlx_model(transcript_path, title)
        if summary_path:
            logseq_path = create_logseq_note(summary_path, title)
            if logseq_path:
                logging.info(f"Logseq note created at: {logseq_path}")
            else:
                logging.error("Failed to create Logseq note.")
        else:
            logging.error("Failed to generate summary.")

        logging.info("End of job for source: local video")

    except Exception as e:
        logging.error(f"An error occurred during processing: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process local video files.")
    parser.add_argument("--input_path", type=str, help="Path to the local video file", required=True)
    parser.add_argument("--title", type=str, help="Title of the video", required=True)

    args = parser.parse_args()

    process_local(args.input_path, args.title)
