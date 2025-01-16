import argparse
import os
import sys
import logging
import traceback
from transcribe.summarize_model import save_summaries, split_text, summarize_in_parallel
from transcribe.transcribe import transcribe
from transcribe.get_video import convert_to_wav, process_local_video
from transcribe.utils import get_filename

# Constants
LOG_FILE = "transcribe.log"
SUMMARIES_DIR = "files/summaries"
LOGSEQ_DIR = "files/logseq"

# Configure logging with more verbose format
logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

def create_logseq_note(summary_path, title):
    """Creates a Logseq note from a summary file.

    Args:
        summary_path: Path to the summary file.
        title: Title of the video/source.

    Returns:
        The path to the created Logseq note.
    Raises:
        FileNotFoundError: If summary file doesn't exist
        IOError: If there's an error writing the note
    """
    if not os.path.exists(summary_path):
        raise FileNotFoundError(f"Summary file not found: {summary_path}")
        
    with open(summary_path, "r") as f:
        lines = f.readlines()
        
    if not lines:
        raise ValueError(f"Summary file is empty: {summary_path}")

    formatted_lines = ["    " + line for line in lines]

    summary_filename = os.path.basename(summary_path)
    logseq_filename = os.path.splitext(summary_filename)[0] + ".md"
    logseq_note_path = os.path.join(LOGSEQ_DIR, logseq_filename)
    os.makedirs(os.path.dirname(logseq_note_path), exist_ok=True)

    with open(logseq_note_path, "w") as f:
        f.write(f"- summarized [[{title}]]\n")
        f.write("- [[summary]]\n")
        f.writelines(formatted_lines)
    
    logging.info(f"Logseq note saved at {logseq_note_path}")
    return logseq_note_path

def call_mlx_model(text_path, title):
    """Summarizes text using the MLX model.

    Args:
        text_path: Path to the text file.
        title: Title of the source.

    Returns:
        The path to the saved summary file.
    Raises:
        FileNotFoundError: If text file doesn't exist
        RuntimeError: If summarization fails
    """
    if not os.path.exists(text_path):
        raise FileNotFoundError(f"Text file not found: {text_path}")
        
    filename_only = get_filename(text_path)
    
    try:
        # Verify text file has content
        if os.path.getsize(text_path) == 0:
            raise ValueError(f"Text file is empty: {text_path}")

        chunks = split_text(text_path=text_path, title=title)
        if not chunks:
            raise RuntimeError("Text splitting produced no chunks")
        logging.info(f"Found {len(chunks)} chunks. Summarizing using MLX model...")

        summaries = summarize_in_parallel(chunks, title)
        if not any(summaries):  # Check if all summaries are None or empty
            raise RuntimeError("No valid summaries were generated")
            
        summary_path = save_summaries(summaries, filename_only)
        logging.info(f"Summary saved at {summary_path}")
        
        # Verify summary was created and has content
        if not os.path.exists(summary_path) or os.path.getsize(summary_path) == 0:
            raise RuntimeError(f"Summary file is empty or missing: {summary_path}")
            
        return summary_path
        
    except Exception as e:
        logging.error(f"Error during MLX model processing: {str(e)}")
        logging.error(traceback.format_exc())
        raise RuntimeError(f"Summarization failed: {str(e)}")

def process_local(input_path, title):
    """Processes a local video file.

    Args:
        input_path: Path to the video file.
        title: Title of the video.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    logging.info(f"Processing local video file: {input_path}")
    
    try:
        # Convert video to audio
        audio_path = process_local_video(input_path)
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            raise RuntimeError(f"Audio extraction failed or produced empty file: {audio_path}")
        logging.info(f"Audio extracted to: {audio_path}")

        # Transcribe audio
        logging.info(f"Transcribing {audio_path} (this may take a while)...")
        elapsed_time, transcript, transcript_path = transcribe(audio_path)
        if not os.path.exists(transcript_path) or os.path.getsize(transcript_path) == 0:
            raise RuntimeError(f"Transcription failed or produced empty file: {transcript_path}")
        logging.info(f"Audio transcribed in {elapsed_time} seconds to: {transcript_path}")

        # Generate summary
        summary_path = call_mlx_model(transcript_path, title)
        
        # Create Logseq note
        logseq_path = create_logseq_note(summary_path, title)
        logging.info(f"Processing completed successfully. Files generated:")
        logging.info(f"  Audio: {audio_path}")
        logging.info(f"  Transcript: {transcript_path}")
        logging.info(f"  Summary: {summary_path}")
        logging.info(f"  Logseq note: {logseq_path}")

    except Exception as e:
        logging.error(f"Error processing video: {str(e)}")
        logging.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process local video files.")
    parser.add_argument("--input_path", type=str, help="Path to the local video file", required=True)
    parser.add_argument("--title", type=str, help="Title of the video", required=True)

    args = parser.parse_args()

    try:
        process_local(args.input_path, args.title)
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
