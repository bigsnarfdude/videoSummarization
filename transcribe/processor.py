from pathlib import Path
import logging
import traceback
from typing import Dict

from config import settings
from .summarize_model import save_summaries, split_text, summarize_in_parallel
from .transcribe import transcribe
from .get_video import process_local_video
from .utils import get_filename
from admin.math_analytics import MathLectureAnalyzer
from admin.lecture_stats import LectureStatsTracker

logger = logging.getLogger(__name__)

def process_video(file_path: Path, title: str) -> Dict:
    """Process video and generate stats"""
    try:
        # Convert video to audio
        audio_path = process_local_video(file_path)
        logger.info(f"Audio extracted to: {audio_path}")

        # Transcribe audio
        elapsed_time, _, transcript_path = transcribe(audio_path)
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

        # Generate and save lecture stats
        analyzer = MathLectureAnalyzer("files/transcripts")
        stats_tracker = LectureStatsTracker()
        
        # Get lecture content
        with open(transcript_path, 'r') as f:
            content = f.read()
            
        # Generate comprehensive stats
        lecture_stats = {
            'basic_info': {
                'title': title,
                'duration': elapsed_time,
                'word_count': len(content.split())
            },
            'complexity': analyzer.analyze_complexity()[0],  # For this specific lecture
            'topics': analyzer.analyze_topic_relationships(content),
            'concept_map': analyzer.generate_concept_map(content),
            'learning_objectives': analyzer.identify_learning_objectives(content),
            'educational_metrics': analyzer.calculate_educational_metrics()[Path(transcript_path).stem]
        }
        
        # Save stats
        lecture_id = Path(transcript_path).stem
        stats_tracker.save_lecture_stats(lecture_id, lecture_stats)
        
        return {
            'audio_path': Path(audio_path),
            'transcript_path': Path(transcript_path),
            'summary_path': Path(summary_path),
            'logseq_path': logseq_path,
            'stats': lecture_stats
        }

    except Exception as e:
        logger.error(f"Error processing video: {e}")
        logger.error(traceback.format_exc())
        raise

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