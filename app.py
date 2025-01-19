import os
import sys
import logging
import logging.handlers
import traceback
import requests
from typing import Optional, Tuple, Dict, Any, List
from flask import send_from_directory, session
from pathlib import Path
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from flask import Flask, request, jsonify, render_template
from config import settings
from transcribe.processor import process_video
from admin.api_routes import api_bp
from admin import admin_bp
from transcribe.get_video import process_local_video
from transcribe.transcribe import transcribe
from transcribe.summarize_model import split_text, summarize_in_parallel, save_summaries
from transcribe.utils import get_filename
from flask_cors import CORS

# Constants for Ollama
OLLAMA_BASE_URL = 'http://localhost:11434'
OLLAMA_TIMEOUT = 120  # Increased timeout for model operations
OLLAMA_RETRY_ATTEMPTS = 3




def init_directories():
    """Initialize all required directories including logs"""
    log_dir = Path('logs')
    os.makedirs(log_dir, exist_ok=True)
    try:
        log_dir.chmod(0o755)
    except Exception as e:
        print(f"Warning: Could not set log directory permissions: {e}")

# Initialize directories before importing settings
init_directories()


def setup_logging():
    """Configure application logging with rotation and proper permissions"""
    try:
        # Application logs
        log_dir = Path(settings.LOG_FILE).parent
        os.makedirs(log_dir, exist_ok=True)

        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

        file_handler = logging.handlers.RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))

        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        logger = logging.getLogger(__name__)
        logger.info("Logging initialized successfully")

        try:
            Path(settings.LOG_FILE).chmod(0o644)
        except Exception as e:
            logger.warning(f"Could not set log file permissions: {e}")

        # Chat logs
        chat_logger = logging.getLogger('chat')
        chat_logger.setLevel(logging.INFO)

        chat_file_handler = logging.handlers.RotatingFileHandler(
            'chat.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        chat_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        chat_logger.addHandler(chat_file_handler)

    except Exception as e:
        print(f"Error setting up logging: {e}", file=sys.stderr)
        raise

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = settings.MAX_FILE_SIZE
app.config['SECRET_KEY'] = settings.SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'

# Register blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


# Use transcripts directory from settings
TRANSCRIPTS_DIR = settings.OUTPUT_DIRS["transcripts"]

def check_ollama_status() -> bool:
    """Check if Ollama service is running and responding"""
    try:
        response = requests.get(f'{OLLAMA_BASE_URL}/api/tags', timeout=5)
        return response.ok
    except:
        return False

def check_model_availability(model_name: str) -> bool:
    """Check if specified model is available in Ollama"""
    try:
        response = requests.post(
            f'{OLLAMA_BASE_URL}/api/show',
            json={"name": model_name},
            timeout=5
        )
        return response.ok
    except:
        return False

def prepare_context(history: List[str], context: str, query: str) -> str:
    """Prepare context for the model"""
    result = ""
    if context:
        result += f"Context:\n{context}\n\n"
    if history:
        result += "Previous conversation:\n"
        for msg in history:
            result += f"- {msg}\n"
    result += f"\nCurrent query: {query}"
    return result


def query_ollama(prompt: str, retries: int = OLLAMA_RETRY_ATTEMPTS) -> str:
    """Query the Ollama API with retries and improved error handling"""
    if not check_ollama_status():
        return "Error: Ollama service is not running. Please start Ollama using 'ollama serve'"

    if not check_model_availability("phi4"):
        return "Error: phi4 model is not available. Please run 'ollama pull phi4'"

    for attempt in range(retries):
        try:
            logger.info(f"Sending request to Ollama (attempt {attempt + 1}/{retries})")
            response = requests.post(
                f'{OLLAMA_BASE_URL}/api/generate',
                json={
                    "model": "phi4:latest",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=OLLAMA_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            logger.info("Successfully received response from Ollama")
            return data.get('response', 'No response received')
        except requests.exceptions.ConnectionError:
            if attempt == retries - 1:
                return "Cannot connect to Ollama. Please check if the service is running."
        except requests.Timeout:
            if attempt == retries - 1:
                return "Request timed out. The model might be loading or the server is busy."
        except Exception as e:
            logger.error(f"Unexpected error querying Ollama: {str(e)}")
            return f"Error: {str(e)}"
    
    return "Error: Maximum retry attempts reached"



@app.route('/ollama/status')
def ollama_status():
    """Endpoint to check Ollama service status"""
    service_status = check_ollama_status()
    model_status = check_model_availability("phi4") if service_status else False
    
    return jsonify({
        'status': 'ok' if service_status and model_status else 'error',
        'details': {
            'service': service_status,
            'model': model_status
        }
    })

@app.route('/list-transcripts')
def list_transcripts():
    """List all available transcript files"""
    try:
        files = list(TRANSCRIPTS_DIR.glob('*.txt'))
        txt_files = [f.name for f in files]
        return jsonify({'files': txt_files}), 200
    except Exception as e:
        logger.error(f"Error listing transcripts: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-latest-transcript')
def get_latest_transcript():
    """Get the most recently processed transcript"""
    try:
        if 'latest_transcript' in session:
            transcript_path = Path(session['latest_transcript'])
            if transcript_path.exists():
                with open(transcript_path, 'r') as f:
                    transcript_text = f.read()
                return jsonify({'transcript': transcript_text})
        return jsonify({'transcript': None})
    except Exception as e:
        logger.error(f"Error reading transcript: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/transcripts/<filename>')
def serve_transcript(filename):
    """Serve a transcript file by name"""
    try:
        return send_from_directory(str(TRANSCRIPTS_DIR), filename, as_attachment=False)
    except FileNotFoundError:
        return jsonify({'error': f"File '{filename}' not found"}), 404

@app.route('/chat')
def chat_page():
    """Render chat interface page"""
    return render_template('chat.html')


@app.route('/ollama/chat', methods=['POST'])
def chat_with_ollama():
    """Handle chat requests with improved error handling"""
    if not request.is_json or not request.get_json(silent=True):
        return jsonify({'error': 'No data provided'}), 400
    
    data = request.get_json()
    query = data.get('query')
    if not query or not str(query).strip():
        return jsonify({'error': 'Query is required'}), 400
        
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        query = data.get('query')
        if not query or not str(query).strip():
            return jsonify({'error': 'Query is required'}), 400

        # Check Ollama status before proceeding
        if not check_ollama_status():
            return jsonify({'error': 'Ollama service is not available'}), 503

        history = data.get('history', [])
        context = data.get('context', '')

        prompt = prepare_context(history, context, str(query))

        # Get the chat logger
        chat_logger = logging.getLogger('chat')

        # Log the chat input
        chat_logger.info(f"User query: {query}")

        response = query_ollama(prompt)

        # Log the chat output
        chat_logger.info(f"Ollama response: {response}")

        if response.startswith('Error:'):
            return jsonify({'error': response}), 500

        return jsonify({'response': response}), 200

    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({
            'error': str(e),
            'details': traceback.format_exc()
        }), 500


def validate_file(file) -> Optional[str]:
    """Validate uploaded file"""
    if not file:
        return "No file provided"
    if not file.filename:
        return "No file selected"
    if len(file.filename) > settings.MAX_FILENAME_LENGTH:
        return f"Filename too long (max {settings.MAX_FILENAME_LENGTH} characters)"
    
    content_length = getattr(file, 'content_length', 0) or 0
    if content_length > settings.MAX_FILE_SIZE:
        return f"File size exceeds {settings.MAX_FILE_SIZE/(1024*1024)}MB limit"
    
    if '.' not in file.filename:
        return "Invalid file format"
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        return "File type not allowed"
    return None

@app.route('/')
def home():
    """Render video upload page"""
    return render_template('index.html')

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

        title = request.form.get('title', Path(file.filename).stem)
        
        try:
            filename = secure_filename(file.filename)
            file_path = settings.OUTPUT_DIRS["uploads"] / filename
            logger.info(f"Saving uploaded file to: {file_path}")
            file.save(file_path)
            logger.info(f"File saved successfully: {file_path}")
            
            logger.info(f"Starting video processing for: {filename}")
            result = process_video(file_path, title)
            
            if result['transcript_path']:
                session['latest_transcript'] = str(result['transcript_path'])
            
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
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Cleaned up uploaded file: {file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up file {file_path}: {e}")

@app.route('/status')
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
        'error': str(e),
        'details': traceback.format_exc(),
        'type': type(e).__name__
    }), 500

if __name__ == '__main__':
    for directory in settings.OUTPUT_DIRS.values():
        os.makedirs(directory, exist_ok=True)
    
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    CORS(app)
    app.run(
        debug=settings.DEBUG,
        host=settings.HOST,
        port=settings.PORT
    )