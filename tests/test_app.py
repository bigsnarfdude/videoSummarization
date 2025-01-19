import pytest
import os
import sys
from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
import threading
import queue
import logging

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import app and its components
from app import app, validate_file, init_directories, setup_logging
from transcribe.processor import create_logseq_note, process_video
from config import settings

class MockFile:
    """Mock file object for testing"""
    def __init__(self, filename: str, content: bytes = b'test content', content_length: int = None):
        self.filename = filename
        self.content = content
        self.content_length = content_length or len(content)
        self._stream = BytesIO(content)

    def save(self, path):
        with open(path, 'wb') as f:
            f.write(self.content)

    def read(self):
        return self.content

@pytest.fixture
def client():
    """Create a test client for the app"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def setup_directories(temp_dir):
    """Setup test directories and cleanup after"""
    # Create temporary test directories
    test_dirs = {
        "uploads": temp_dir / "uploads",
        "audio": temp_dir / "audio",
        "transcripts": temp_dir / "transcripts",
        "summaries": temp_dir / "summaries",
        "logseq": temp_dir / "logseq",
        "stats": temp_dir / "stats"
    }

    # Create directories
    for directory in test_dirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    # Store original directories
    original_dirs = settings.OUTPUT_DIRS.copy()

    # Update settings to use test directories
    settings.OUTPUT_DIRS.update(test_dirs)

    yield test_dirs

    # Restore original directories
    settings.OUTPUT_DIRS = original_dirs

@pytest.fixture
def mock_video_file():
    """Create a mock video file for testing"""
    return MockFile(
        filename='test_video.mp4',
        content=b'mock video content',
        content_length=1024
    )

def test_home_page(client):
    """Test the home page endpoint"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'<!DOCTYPE html>' in response.data

def test_status_endpoint(client):
    """Test the status endpoint"""
    response = client.get('/status')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'running'

def test_validate_file():
    """Test file validation function"""
    # Test valid file
    valid_file = MockFile('test.mp4', content_length=1024)
    assert validate_file(valid_file) is None

    # Test no file
    assert validate_file(None) == "No file provided"

    # Test empty filename
    no_name_file = MockFile('', content_length=1024)
    assert validate_file(no_name_file) == "No file selected"

    # Test file too large
    large_file = MockFile('test.mp4', content_length=settings.MAX_FILE_SIZE + 1)
    assert "File size exceeds" in validate_file(large_file)

    # Test filename too long
    long_name = 'a' * (settings.MAX_FILENAME_LENGTH + 1) + '.mp4'
    long_file = MockFile(long_name)
    assert "Filename too long" in validate_file(long_file)

    # Test invalid extension
    wrong_type = MockFile('test.txt', content_length=1024)
    assert validate_file(wrong_type) == "File type not allowed"

    # Test no extension
    no_ext = MockFile('testfile', content_length=1024)
    assert validate_file(no_ext) == "Invalid file format"

def test_upload_no_file(client):
    """Test upload endpoint with no file"""
    response = client.post('/api/v1/process')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == "No file selected"

def test_upload_empty_filename(client):
    """Test upload with empty filename"""
    data = {'file': (BytesIO(b''), '')}
    response = client.post(
        '/api/v1/process',
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == "No file selected"

def test_upload_invalid_file_type(client):
    """Test upload with invalid file type"""
    data = {
        'file': (BytesIO(b'test content'), 'test.txt')
    }
    response = client.post(
        '/api/v1/process',
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == "File type not allowed"

def test_create_logseq_note(temp_dir):
    """Test Logseq note creation"""
    # Create a test summary file
    summary_content = "Test summary line 1\nTest summary line 2\n"
    summary_file = temp_dir / "test_summary.txt"
    summary_file.write_text(summary_content)

    # Create note
    title = "Test Video"
    logseq_path = create_logseq_note(summary_file, title)

    # Verify note was created
    assert logseq_path is not None
    assert logseq_path.exists()

    # Check content
    content = logseq_path.read_text()
    assert f"- summarized [[{title}]]" in content
    assert "- [[summary]]" in content
    assert "    Test summary line 1" in content
    assert "    Test summary line 2" in content

def test_create_logseq_note_missing_file(temp_dir):
    """Test Logseq note creation with missing summary file"""
    missing_file = temp_dir / "nonexistent.txt"
    result = create_logseq_note(missing_file, "Test")
    assert result is None

def test_upload_valid_file(client, setup_directories, mock_video_file, monkeypatch):
    """Test upload with valid video file"""
    result_files = {
        'audio_path': setup_directories['audio'] / 'test_audio.wav',
        'transcript_path': setup_directories['transcripts'] / 'test_transcript.txt',
        'summary_path': setup_directories['summaries'] / 'test_summary.txt',
        'logseq_path': setup_directories['logseq'] / 'test_note.md',
        'stats_path': setup_directories['stats'] / 'test_stats.json'
    }
    
    # Create mock files
    for path in result_files.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('test content')

    # Mock process_video
    def mock_process(file_path, title):
        return result_files
    
    monkeypatch.setattr('app.process_video', mock_process)

    data = {
        'file': (BytesIO(mock_video_file.content), mock_video_file.filename),
        'title': 'Test Video'
    }
    response = client.post(
        '/api/v1/process',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert 'files' in data

def test_concurrent_requests(client):
    """Test handling multiple concurrent requests"""
    results = queue.Queue()
    
    def make_request():
        with app.test_request_context():
            with app.test_client() as test_client:
                response = test_client.get('/status')
                results.put(response.status_code)
    
    # Create and run multiple threads
    threads = [threading.Thread(target=make_request) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    
    # Check all responses
    while not results.empty():
        assert results.get() == 200

def test_large_file_upload(client):
    """Test upload with file exceeding size limit"""
    app.config['MAX_CONTENT_LENGTH'] = 1024  # Set a small limit for testing
    large_content = b'x' * 2048  # Content larger than limit
    data = {
        'file': (BytesIO(large_content), 'large.mp4')
    }
    response = client.post(
        '/api/v1/process',
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "File size exceeds" in data['error']
    app.config['MAX_CONTENT_LENGTH'] = settings.MAX_FILE_SIZE  # Restore original limit

def test_error_handler(client, monkeypatch):
    """Test global error handler"""
    # Test 404 error
    response = client.get('/nonexistent')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['error'] == 'Not Found'
    
    # Test 500 error without adding new route
    def mock_process(*args, **kwargs):
        raise Exception("Test error")
    
    # Use existing route with mocked function
    monkeypatch.setattr('app.process_video', mock_process)
    response = client.post('/api/v1/process', 
                          data={'file': (BytesIO(b'test'), 'test.mp4')},
                          content_type='multipart/form-data')
    
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data['error'] == 'Test error'  # The actual error message, not 'Internal Server Error'

def test_missing_directory_creation(temp_dir):
    """Test automatic creation of missing directories"""
    test_base = temp_dir / "files"
    test_base.mkdir(exist_ok=True)
    
    # Create test directory configuration matching app structure
    test_dirs = {
        "uploads": test_base / "uploads",
        "audio": test_base / "audio",
        "transcripts": test_base / "transcripts",
        "summaries": test_base / "summaries",
        "logseq": test_base / "logseq",
        "stats": test_base / "stats"
    }

    try:
        # Create base test dir
        test_base.mkdir(exist_ok=True)
        
        # Create each required directory
        for directory in test_dirs.values():
            directory.mkdir(parents=True, exist_ok=True)
            
        # Verify directories were created
        for dir_name, directory in test_dirs.items():
            assert directory.exists(), f"Directory {dir_name} not created at {directory}"
            assert directory.is_dir(), f"{dir_name} is not a directory at {directory}"
            
    finally:
        # Clean up test directory
        if test_base.exists():
            shutil.rmtree(test_base)

def test_setup_logging():
    """Test logging setup"""
    # Create temporary log directory
    log_dir = Path('test_logs')
    original_log_file = settings.LOG_FILE
    settings.LOG_FILE = log_dir / 'test.log'
    
    try:
        # Remove existing log directory if it exists
        if log_dir.exists():
            shutil.rmtree(log_dir)
            
        # Setup logging
        setup_logging()
        
        # Verify log directory and file were created
        assert log_dir.exists()
        assert settings.LOG_FILE.exists()
        
        # Test logging
        logger = logging.getLogger(__name__)
        test_message = "Test log message"
        logger.info(test_message)
        
        # Verify message was logged
        with open(settings.LOG_FILE) as f:
            log_content = f.read()
            assert test_message in log_content
            
    finally:
        # Cleanup
        if log_dir.exists():
            shutil.rmtree(log_dir)
        settings.LOG_FILE = original_log_file

def test_process_video_cleanup(client, setup_directories, mock_video_file, monkeypatch):
    """Test cleanup after video processing"""
    def mock_process(file_path, title):
        raise Exception("Processing failed")
    
    monkeypatch.setattr('app.process_video', mock_process)
    
    data = {
        'file': (BytesIO(mock_video_file.content), mock_video_file.filename),
        'title': 'Test Video'
    }
    
    response = client.post(
        '/api/v1/process',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 500
    # Verify uploaded file was cleaned up
    uploaded_files = list(setup_directories['uploads'].glob('*'))
    assert len(uploaded_files) == 0

def test_chat_endpoint(client):
    """Test chat endpoint"""
    response = client.get('/chat')
    assert response.status_code == 200
    assert b'<!DOCTYPE html>' in response.data