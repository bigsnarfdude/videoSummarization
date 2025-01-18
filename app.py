from flask import Flask, request, jsonify, render_template
import logging
import traceback
import os
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from config import settings
from transcribe.processor import process_video
from admin.api_routes import api_bp
from admin import admin_bp
from transcribe.get_video import process_local_video
from transcribe.transcribe import transcribe


# Initialize Flask app
app = Flask(__name__)

# Configure app from settings
app.config['MAX_CONTENT_LENGTH'] = settings.MAX_FILE_SIZE
app.config['SECRET_KEY'] = settings.SECRET_KEY

# Register blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Configure logging
logging.basicConfig(
    filename=settings.LOG_FILE,
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

@app.route(f'{settings.API_PREFIX}/process', methods=['POST'])
def process_video_endpoint() -> Tuple[Dict[str, Any], int]:
    """Process video upload endpoint"""
    file_path = None
    try:
        if 'file' not in request.files:
            logger.error("No file in request")
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if not file.filename:
            logger.error("Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        error = validate_file(file)
        if error:
            logger.error(f"File validation error: {error}")
            return jsonify({'error': error}), 400

        # Get title from form data or use filename
        title = request.form.get('title', Path(file.filename).stem)
        
        # Save and process file
        try:
            filename = secure_filename(file.filename)
            file_path = settings.OUTPUT_DIRS["uploads"] / filename
            file.save(file_path)
            logger.info(f"File saved to: {file_path}")
            
            # Process the video
            result = process_video(file_path, title)
            
            response = {
                'status': 'success',
                'files': {
                    'audio': str(result['audio_path'].name),
                    'transcript': str(result['transcript_path'].name),
                    'summary': str(result['summary_path'].name),
                    'logseq': str(result['logseq_path'].name)
                }
            }
            logger.info(f"Successfully processed video. Response: {response}")
            return jsonify(response), 200
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Processing error: {error_details}")
            return jsonify({
                'error': str(e),
                'details': error_details,
                'type': type(e).__name__
            }), 500
            
    except RequestEntityTooLarge:
        max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
        return jsonify({'error': f"File size exceeds {max_mb}MB limit"}), 400
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"API error: {error_details}")
        return jsonify({
            'error': str(e),
            'details': error_details,
            'type': type(e).__name__
        }), 500
    finally:
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Cleaned up uploaded file: {file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up file {file_path}: {e}")


def init_directories():
    """Initialize all required directories"""
    for directory in settings.OUTPUT_DIRS.values():
        os.makedirs(directory, exist_ok=True)

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
        
    if hasattr(file, 'content_length') and file.content_length > settings.MAX_FILE_SIZE:
        return f"File size exceeds {settings.MAX_FILE_SIZE/(1024*1024)}MB limit"
        
    if '.' not in file.filename:
        return "Invalid file format"
        
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
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

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested URL was not found on the server.'
    }), 404

@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    """Handle large file upload errors"""
    max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
    return jsonify({
        'error': f"File size exceeds {max_mb}MB limit"
    }), 400

@app.errorhandler(Exception)
def handle_exception(e):
    """Handle any uncaught exception"""
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    
    return jsonify({
        'error': 'Internal Server Error',
        'message': str(e),
        'details': traceback.format_exc()
    }), 500

@app.route(f'{settings.API_PREFIX}/status', methods=['GET'])
def status() -> Tuple[Dict[str, str], int]:
    """Health check endpoint"""
    return jsonify({'status': 'running'}), 200

# Initialize directories when app is imported
init_directories()


if __name__ == '__main__':
    # Initialize directories when app is run directly
    init_directories()
    
    # Run the Flask app
    print(f"Starting server on {settings.HOST}:{settings.PORT}")
    print(f"Debug mode: {settings.DEBUG}")
    app.run(
        debug=settings.DEBUG,
        host=settings.HOST,
        port=settings.PORT
    )