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

# Configure logging to both file and console
def setup_logging():
    # Create a formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Set up file handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    
    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def create_logseq_note(summary_path, title):
    """Creates a Logseq note from a summary file."""
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
    
    logging.info(f"✓ Created Logseq note: {logseq_note_path}")
    return logseq_note_path

def call_mlx_model(text_path, title):
    """Summarizes text using the MLX model."""
    if not os.path.exists(text_path):
        raise FileNotFoundError(f"Text file not found: {text_path}")
        
    filename_only = get_filename(text_path)
    
    try:
        if os.path.getsize(text_path) == 0:
            raise ValueError(f"Text file is empty: {text_path}")

        logging.info("Starting text splitting...")
        chunks = split_text(text_path=text_path, title=title)
        if not chunks:
            raise RuntimeError("Text splitting produced no chunks")
        logging.info(f"✓ Split text into {len(chunks)} chunks")

        logging.info("Generating summaries...")
        summaries = summarize_in_parallel(chunks, title)
        if not any(summaries):
            raise RuntimeError("No valid summaries were generated")
            
        summary_path = save_summaries(summaries, filename_only)
        logging.info(f"✓ Created summary: {summary_path}")
        
        if not os.path.exists(summary_path) or os.path.getsize(summary_path) == 0:
            raise RuntimeError(f"Summary file is empty or missing: {summary_path}")
            
        return summary_path
        
    except Exception as e:
        logging.error(f"Summarization failed: {str(e)}")
        logging.debug(traceback.format_exc())
        raise

def process_local(input_path, title):
    """Processes a local video file."""
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    logging.info(f"Starting processing of: {input_path}")
    
    try:
        logging.info("Converting video to audio...")
        audio_path = process_local_video(input_path)
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            raise RuntimeError(f"Audio extraction failed or produced empty file: {audio_path}")
        logging.info(f"✓ Created audio file: {audio_path}")

        logging.info("Starting transcription (this may take several minutes)...")
        elapsed_time, transcript, transcript_path = transcribe(audio_path)
        if not os.path.exists(transcript_path) or os.path.getsize(transcript_path) == 0:
            raise RuntimeError(f"Transcription failed or produced empty file: {transcript_path}")
        logging.info(f"✓ Completed transcription in {elapsed_time} seconds")
        logging.info(f"✓ Created transcript: {transcript_path}")

        logging.info("Starting summarization...")
        summary_path = call_mlx_model(transcript_path, title)
        logging.info("✓ Completed summarization")
        
        logging.info("Creating Logseq note...")
        logseq_path = create_logseq_note(summary_path, title)
        
        logging.info("\nProcessing completed successfully!")
        logging.info("Generated files:")
        logging.info(f"  Audio:      {audio_path}")
        logging.info(f"  Transcript: {transcript_path}")
        logging.info(f"  Summary:    {summary_path}")
        logging.info(f"  Logseq:     {logseq_path}")

    except Exception as e:
        logging.error(f"Processing failed: {str(e)}")
        logging.debug(traceback.format_exc())
        raise

if __name__ == "__main__":
    # Set up logging before anything else
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Process local video files.")
    parser.add_argument("--input_path", type=str, help="Path to the local video file", required=True)
    parser.add_argument("--title", type=str, help="Title of the video", required=True)

    args = parser.parse_args()

    try:
        process_local(args.input_path, args.title)
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)
