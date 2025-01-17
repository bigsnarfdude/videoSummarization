from flask import Flask, request, jsonify, render_template
import os
import logging
import traceback
from werkzeug.utils import secure_filename
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from config import settings
from transcribe.summarize_model import save_summaries, split_text, summarize_in_parallel
from transcribe.transcribe import transcribe
from transcribe.get_video import process_local_video
from transcribe.utils import get_filename

# Initialize Flask app
app = Flask(__name__)

# Configure app from settings
app.config['MAX_CONTENT_LENGTH'] = settings.MAX_FILE_SIZE
app.config['SECRET_KEY'] = settings.SECRET_KEY

# Configure logging
logging.basicConfig(
    filename=settings.LOG_FILE,
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

def allowed_file(filename: str) -> bool:
    """
    Check if the file has an allowed extension.
    
    Args:
        filename: The filename to check
        
    Returns:
        bool: True if file extension is allowed
    """
    if '.' not in filename:
        return False
        
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in settings.ALLOWED_EXTENSIONS

def validate_file(file) -> Optional[str]:
    """
    Validate uploaded file and return error message if invalid.
    
    Args:
        file: The uploaded file object
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not file:
        return "No file provided"
    if not file.filename:
        return "No file selected"
    if len(file.filename) > settings.MAX_FILENAME_LENGTH:
        return f"Filename too long (max {settings.MAX_FILENAME_LENGTH} characters)"
    if not allowed_file(file.filename):
        return "File type not allowed"
    return None

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
        
        return {
            'audio_path': Path(audio_path),
            'transcript_path': Path(transcript_path),
            'summary_path': Path(summary_path),
            'logseq_path': logseq_path
        }

    except Exception as e:
        logger.error(f"Error processing video: {e}")
        logger.error(traceback.format_exc())
        raise

@app.route('/')
def home():
    """Render the home page"""
    return render_template('index.html')

@app.route(f'{settings.API_PREFIX}/process', methods=['POST'])
def process_video_endpoint() -> Tuple[Dict[str, Any], int]:
    """
    API endpoint to process a video file
    
    Returns:
        Tuple[Dict, int]: Response data and status code
    """
    file_path = None
    try:
        # Validate request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        error = validate_file(file)
        if error:
            return jsonify({'error': error}), 400

        # Get title from form data or use filename
        title = request.form.get('title', Path(file.filename).stem)
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        file_path = settings.OUTPUT_DIRS["uploads"] / filename
        file.save(file_path)
        logger.info(f"File saved to: {file_path}")
        
        try:
            # Process the video
            result = process_video(file_path, title)
            
            # Verify files exist and have content
            for key, path in result.items():
                if not path.exists():
                    raise RuntimeError(f"Generated file {key} does not exist: {path}")
                if path.stat().st_size == 0:
                    raise RuntimeError(f"Generated file {key} is empty: {path}")
                    
            # Return paths to generated files
            return jsonify({
                'status': 'success',
                'files': {
                    'audio': str(result['audio_path'].name),
                    'transcript': str(result['transcript_path'].name),
                    'summary': str(result['summary_path'].name),
                    'logseq': str(result['logseq_path'].name)
                }
            }), 200
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Processing error: {error_details}")
            return jsonify({
                'error': str(e),
                'details': error_details,
                'type': type(e).__name__
            }), 500
            
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"API error: {error_details}")
        return jsonify({
            'error': str(e),
            'details': error_details,
            'type': type(e).__name__
        }), 500
        
    finally:
        # Clean up uploaded file
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Cleaned up uploaded file: {file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up file {file_path}: {e}")

@app.route(f'{settings.API_PREFIX}/status', methods=['GET'])
def status() -> Tuple[Dict[str, str], int]:
    """Health check endpoint"""
    return jsonify({'status': 'running'}), 200

if __name__ == '__main__':
    app.run(
        debug=settings.DEBUG,
        host=settings.HOST,
        port=settings.PORT
    )
