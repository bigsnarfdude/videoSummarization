from pathlib import Path
import logging
import traceback
import json
import os
from datetime import datetime
from typing import Dict

from config import settings
from .summarize_model import save_summaries, split_text, summarize_in_parallel
from .transcribe import transcribe
from .get_video import process_local_video
from .utils import get_filename
from admin.math_analytics import MathLectureAnalyzer
from admin.lecture_stats import LectureStatsTracker

logger = logging.getLogger(__name__)

def create_logseq_note(summary_path: Path, title: str) -> Path:
    """Creates a Logseq note from a summary file"""
    try:
        with open(summary_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.error(f"Summary file not found: {summary_path}")
        return None

    formatted_lines = ["    " + line for line in lines]
    logseq_filename = summary_path.stem + ".md"
    logseq_path = settings.OUTPUT_DIRS["logseq"] / logseq_filename

    try:
        with open(logseq_path, "w") as f:
            f.write(f"- summarized [[{title}]]\n")
            f.write("- [[summary]]\n")
            f.writelines(formatted_lines)
        logger.info(f"Logseq note saved at {logseq_path}")
        return logseq_path
    except IOError as e:
        logger.error(f"Error writing Logseq note: {e}")
        return None

def process_video(file_path: Path, title: str) -> Dict[str, Path]:
    """
    Process a video file and return all generated file paths
    
    Args:
        file_path: Path to the video file
        title: Title of the video
        
    Returns:
        Dict[str, Path]: Paths to all generated files
        
    Raises:
        RuntimeError: If any processing step fails
    """
    try:
        # Convert video to audio
        audio_path = process_local_video(file_path)
        logger.info(f"Audio extracted to: {audio_path}")

        # Transcribe audio
        elapsed_time, transcript_text, transcript_path = transcribe(audio_path)
        logger.info(f"Audio transcribed in {elapsed_time} seconds")

        # Generate summary
        chunks = split_text(text_path=transcript_path, title=title)
        logger.info(f"Found {len(chunks)} chunks. Summarizing...")
        
        summaries = summarize_in_parallel(chunks, title)
        summary_path = save_summaries(summaries, get_filename(transcript_path))
        logger.info(f"Summary saved at {summary_path}")

        # Create Logseq note
        logseq_path = create_logseq_note(Path(summary_path), title)
        if not logseq_path:
            raise RuntimeError("Failed to create Logseq note")

        # Generate and save stats
        stats_path = None
        try:
            logger.info(f"Starting stats generation for {title}")
            
            # Read transcript text to count words
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript_content = f.read()
                word_count = len(transcript_content.split())
                logger.info(f"Counted {word_count} words in transcript")
            except Exception as e:
                logger.error(f"Error reading transcript for word count: {e}")
                word_count = 0
            
            stats = {
                'metadata': {
                    'title': title,
                    'processing_time': elapsed_time,
                    'timestamp': datetime.now().isoformat(),
                    'source_file': str(file_path.name),
                },
                'analysis': {
                    'word_count': word_count,
                    'chunk_count': len(chunks),
                    'summary_count': len(summaries),
                    'audio_duration': None,  # TODO: Add audio duration
                }
            }
            
            logger.info(f"Generated stats data: {stats}")
            
            # Ensure stats directory exists and is writable
            stats_dir = settings.OUTPUT_DIRS["stats"]
            stats_dir.mkdir(parents=True, exist_ok=True)
            
            # Verify directory exists and is writable
            if not stats_dir.exists():
                raise RuntimeError(f"Stats directory does not exist: {stats_dir}")
            if not os.access(stats_dir, os.W_OK):
                raise RuntimeError(f"Stats directory is not writable: {stats_dir}")
            
            # Save stats file
            filename_base = get_filename(transcript_path)
            stats_path = stats_dir / f"{filename_base}_stats.json"
            
            logger.info(f"Attempting to write stats to: {stats_path}")
            
            try:
                with open(stats_path, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, indent=2, ensure_ascii=False)
                logger.info(f"Successfully wrote stats to: {stats_path}")
                
                # Verify file was written
                if not stats_path.exists():
                    raise RuntimeError(f"Stats file was not created: {stats_path}")
                
                # Verify file has content
                if stats_path.stat().st_size == 0:
                    raise RuntimeError(f"Stats file is empty: {stats_path}")
                
                logger.info(f"Verified stats file exists and has content: {stats_path}")
            except Exception as e:
                logger.error(f"Error writing stats file: {e}")
                raise
            
        except Exception as e:
            logger.error(f"Error generating stats: {e}")
            logger.error(traceback.format_exc())
            # Continue processing even if stats generation fails
            
        result = {
            'audio_path': Path(audio_path),
            'transcript_path': Path(transcript_path),
            'summary_path': Path(summary_path),
            'logseq_path': logseq_path,
        }
        
        if stats_path and stats_path.exists():
            result['stats_path'] = stats_path
            
        return result

    except Exception as e:
        logger.error(f"Error processing video: {e}")
        logger.error(traceback.format_exc())
        raise