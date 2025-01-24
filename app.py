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

OLLAMA_BASE_URL = 'http://localhost:11434'
OLLAMA_TIMEOUT = 120
OLLAMA_RETRY_ATTEMPTS = 3

app = Flask(__name__, 
    template_folder=Path(__file__).parent / "templates",
    static_folder=Path(__file__).parent / "static"
)

# Then add a proper root route:
@app.route('/')
def index():
    return render_template('index.html')


def init_directories():
    """Initialize required directories"""
    log_dir = Path('logs')
    os.makedirs(log_dir, exist_ok=True)
    try:
        log_dir.chmod(0o755)
    except Exception as e:
        print(f"Warning: Could not set log directory permissions: {e}")

init_directories()

def setup_logging():
    """Configure application logging"""
    try:
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

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = settings.MAX_FILE_SIZE
app.config['SECRET_KEY'] = settings.SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'

app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

setup_logging()
logger = logging.getLogger(__name__)

TRANSCRIPTS_DIR = settings.OUTPUT_DIRS["transcripts"]

# [Keep all the existing route handlers and helper functions]

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
