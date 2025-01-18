import os
import sys
from pathlib import Path
import logging
import logging.handlers
import traceback
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from typing import Dict, Optional, Tuple, Any
from flask import Flask, request, jsonify, render_template

# First, ensure required directories exist
def init_directories():
    """Initialize all required directories including logs"""
    # Create logs directory first
    log_dir = Path('logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Set proper permissions
    try:
        log_dir.chmod(0o755)  # rwxr-xr-x
    except Exception as e:
        print(f"Warning: Could not set log directory permissions: {e}")

# Initialize directories before importing settings or other modules
init_directories()

# Now import settings and other modules
from config import settings
from transcribe.processor import process_video
from admin.api_routes import api_bp
from admin import admin_bp
from transcribe.get_video import process_local_video
from transcribe.transcribe import transcribe
from transcribe.summarize_model import (
    split_text,
    summarize_in_parallel,
    save_summaries
)
from transcribe.utils import get_filename

def setup_logging():
    """Configure application logging with rotation and proper permissions"""
    try:
        # Create logs directory if it doesn't exist
        log_dir = Path(settings.LOG_FILE).parent
        os.makedirs(log_dir, exist_ok=True)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))

        # Add handlers to root logger
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Test logging
        logger = logging.getLogger(__name__)
        logger.info("Logging initialized successfully")
        
        # Set proper permissions for log file
        try:
            Path(settings.LOG_FILE).chmod(0o644)  # rw-r--r--
        except Exception as e:
            logger.warning(f"Could not set log file permissions: {e}")

    except Exception as e:
        print(f"Error setting up logging: {e}", file=sys.stderr)
        raise

# Initialize Flask app
app = Flask(__name__)

# Configure app
app.config['MAX_CONTENT_LENGTH'] = settings.MAX_FILE_SIZE
app.config['SECRET_KEY'] = settings.SECRET_KEY

# Register blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

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
            logger.info(f"Saving uploaded file to: {file_path}")
            file.save(file_path)
            logger.info(f"File saved successfully: {file_path}")
            
            # Process the video
            logger.info(f"Starting video processing for: {filename}")
            result = process_video(file_path, title)
            
            response = {
                'status': 'success',
                'files': {
                    'audio': str(result['audio_path'].name),
                    'transcript': str(result['transcript_path'].name),
                    'summary': str(result['summary_path'].name),
                    'logseq': str(result['logseq_path'].name),
                    'stats': f"{Path(result['transcript_path']).stem}_stats.json"
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
        logger.error(f"File size exceeds limit: {max_mb}MB")
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
        # Clean up uploaded file
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Cleaned up uploaded file: {file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up file {file_path}: {e}")

@app.route('/')
def home():
    """Render the home page"""
    return render_template('index.html')

@app.route(f'{settings.API_PREFIX}/status', methods=['GET'])
def status() -> Tuple[Dict[str, str], int]:
    """Health check endpoint"""
    return jsonify({'status': 'running'}), 200

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    logger.warning(f"404 error: {request.url}")
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested URL was not found on the server.'
    }), 404

@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    """Handle large file upload errors"""
    max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
    logger.warning(f"File size exceeded {max_mb}MB limit")
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

if __name__ == '__main__':
    # Initialize all directories
    for directory in settings.OUTPUT_DIRS.values():
        os.makedirs(directory, exist_ok=True)
    
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    app.run(
        debug=settings.DEBUG,
        host=settings.HOST,
        port=settings.PORT
    )
