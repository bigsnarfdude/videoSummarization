from pathlib import Path
import logging
import traceback
import json
import os
from datetime import datetime
from typing import Dict, Optional

from config import settings
from .summarize_model import save_summaries, split_text, summarize_in_parallel
from .transcribe import transcribe
from .get_video import process_local_video
from .utils import get_filename
from admin.math_analytics import MathLectureAnalyzer

logger = logging.getLogger(__name__)

def create_logseq_note(summary_path: Path, title: str) -> Optional[Path]:
    """
    Creates a Logseq note from a summary file.
    
    Args:
        summary_path: Path to the summary file
        title: Title of the video
        
    Returns:
        Optional[Path]: Path to created Logseq note, None if creation fails
    """
    try:
        # Check if summary file exists
        if not summary_path.exists():
            logger.error(f"Summary file not found: {summary_path}")
            return None
            
        # Read summary content
        with open(summary_path, "r", encoding='utf-8') as f:
            lines = f.readlines()
            
        if not lines:
            logger.error(f"Summary file is empty: {summary_path}")
            return None

        # Format lines with proper indentation
        formatted_lines = ["    " + line for line in lines]

        # Create logseq note filename and path
        logseq_filename = summary_path.stem + ".md"
        logseq_path = settings.OUTPUT_DIRS["logseq"] / logseq_filename

        # Ensure logseq directory exists
        logseq_path.parent.mkdir(parents=True, exist_ok=True)

        # Write logseq note with formatted content
        try:
            with open(logseq_path, "w", encoding='utf-8') as f:
                f.write(f"- summarized [[{title}]]\n")
                f.write("- [[summary]]\n")
                f.writelines(formatted_lines)
                
            logger.info(f"Logseq note saved at {logseq_path}")
            return logseq_path
            
        except IOError as e:
            logger.error(f"Error writing Logseq note: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating Logseq note: {e}")
        logger.error(traceback.format_exc())
        return None

def analyze_transcript_content(transcript_path: Path, analyzer: MathLectureAnalyzer) -> Dict:
    """
    Analyze transcript content using MathLectureAnalyzer.
    
    Args:
        transcript_path: Path to transcript file
        analyzer: MathLectureAnalyzer instance
        
    Returns:
        Dict containing analysis results
    """
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Perform various analyses
        topic_analysis = analyzer.analyze_topic_relationships(content)
        concept_map = analyzer.generate_concept_map(content)
        learning_obj = analyzer.identify_learning_objectives(content)
        complexity = analyzer.analyze_complexity()
        
        analysis_results = {
            'topics': {
                'core_topics': topic_analysis.get('core_topics', []),
                'dependencies': topic_analysis.get('dependencies', []),
                'theoretical_links': topic_analysis.get('theoretical_links', [])
            },
            'concepts': {
                'key_concepts': concept_map.get('concepts', []),
                'relationships': concept_map.get('relationships', []),
                'prerequisites': concept_map.get('prerequisites', []),
                'applications': concept_map.get('applications', [])
            },
            'learning_objectives': learning_obj,
            'complexity_analysis': complexity[0] if complexity else {}
        }
        
        logger.info(f"Successfully analyzed transcript content: {transcript_path}")
        return analysis_results
        
    except Exception as e:
        logger.error(f"Error analyzing transcript content: {e}")
        logger.error(traceback.format_exc())
        return {}

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

        # Initialize MathLectureAnalyzer without directory since we're analyzing a single file
        analyzer = MathLectureAnalyzer()

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

        # Analyze transcript content
        content_analysis = analyze_transcript_content(Path(transcript_path), analyzer)

        # Generate and save stats
        try:
            logger.info(f"Starting stats generation for {title}")
            
            # Read transcript text to count words
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_content = f.read()
                word_count = len(transcript_content.split())
                logger.info(f"Counted {word_count} words in transcript")
            
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
                    'audio_duration': None,
                    'topics': content_analysis.get('topics', {}),
                    'concepts': content_analysis.get('concepts', {}),
                    'learning_objectives': content_analysis.get('learning_objectives', {}),
                    'complexity': content_analysis.get('complexity_analysis', {})
                }
            }
            
            logger.info(f"Generated stats data: {stats}")
            
            # Ensure stats directory exists and is writable
            stats_dir = settings.OUTPUT_DIRS["stats"]
            stats_dir.mkdir(parents=True, exist_ok=True)
            
            # Save stats file
            filename_base = get_filename(transcript_path)
            stats_path = stats_dir / f"{filename_base}_stats.json"
            
            logger.info(f"Attempting to write stats to: {stats_path}")
            
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
            logger.info(f"Successfully wrote stats to: {stats_path}")
            
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
            logger.error(f"Error generating stats: {e}")
            logger.error(traceback.format_exc())
            raise
            
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        logger.error(traceback.format_exc())
        raise