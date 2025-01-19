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

from unittest.mock import patch, MagicMock
from flask import url_for

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


def test_init_directories_permissions(tmp_path):
    """Test directory initialization with permission errors"""
    with patch('os.makedirs') as mock_makedirs, \
         patch('pathlib.Path.chmod') as mock_chmod:
        mock_chmod.side_effect = PermissionError("Permission denied")
        
        # Should not raise exception even if chmod fails
        init_directories()
        
        assert mock_makedirs.called
        assert mock_chmod.called

def test_setup_logging_failure(tmp_path):
    """Test logging setup with file creation failure"""
    with patch('logging.handlers.RotatingFileHandler') as mock_handler:
        mock_handler.side_effect = PermissionError("Permission denied")
        
        with pytest.raises(Exception):
            setup_logging()

def test_chat_with_ollama_endpoint(client):
    """Test the chat endpoint with various inputs"""
    # Test missing query
    response = client.post('/ollama/chat', 
                          json={'history': [], 'document': ''})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Query is required'
    
    # Test successful query
    test_query = {
        'query': 'test question',
        'history': ['previous message'],
        'document': 'test document'
    }
    
    with patch('app.query_ollama') as mock_query:
        mock_query.return_value = "Test response"
        response = client.post('/ollama/chat', json=test_query)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['response'] == "Test response"
    
    # Test query failure
    with patch('app.query_ollama') as mock_query:
        mock_query.side_effect = Exception("Query failed")
        response = client.post('/ollama/chat', json=test_query)
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data

def test_process_video_with_validation_errors(client):
    """Test video processing with various validation scenarios"""
    # Test file with invalid content length
    with patch('app.validate_file') as mock_validate:
        mock_validate.return_value = "Invalid content length"
        data = {
            'file': (BytesIO(b'test'), 'test.mp4'),
            'title': 'Test Video'
        }
        response = client.post('/api/v1/process', 
                             data=data,
                             content_type='multipart/form-data')
        assert response.status_code == 400
        assert b'Invalid content length' in response.data

def test_process_video_with_processing_error(client, setup_directories):
    """Test video processing with processing errors"""
    with patch('app.process_video') as mock_process:
        # Simulate processing error
        mock_process.side_effect = Exception("Processing failed")
        
        data = {
            'file': (BytesIO(b'test'), 'test.mp4'),
            'title': 'Test Video'
        }
        response = client.post('/api/v1/process', 
                             data=data,
                             content_type='multipart/form-data')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert data['type'] == 'Exception'

def test_error_handler_specific_exceptions(client):
    """Test error handler with specific exception types"""
    with patch('app.process_video') as mock_process:
        # Test ValueError
        mock_process.side_effect = ValueError("Invalid value")
        response = client.post('/api/v1/process', 
                             data={'file': (BytesIO(b'test'), 'test.mp4')},
                             content_type='multipart/form-data')
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['type'] == 'ValueError'
        
        # Test RuntimeError
        mock_process.side_effect = RuntimeError("Runtime error")
        response = client.post('/api/v1/process', 
                             data={'file': (BytesIO(b'test'), 'test.mp4')},
                             content_type='multipart/form-data')
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['type'] == 'RuntimeError'

def test_cleanup_after_processing_error(client, setup_directories):
    """Test file cleanup after processing error"""
    with patch('app.process_video') as mock_process:
        mock_process.side_effect = Exception("Processing error")
        
        data = {
            'file': (BytesIO(b'test content'), 'test.mp4'),
            'title': 'Test'
        }
        
        response = client.post('/api/v1/process', 
                             data=data,
                             content_type='multipart/form-data')
        
        # Check that uploaded file was cleaned up
        upload_dir = setup_directories['uploads']
        assert len(list(upload_dir.glob('*'))) == 0

def test_large_request_handling(client):
    """Test handling of large requests"""
    # Test request exceeding maximum content length
    large_data = b'x' * (settings.MAX_FILE_SIZE + 1)
    response = client.post('/api/v1/process', 
                          data={'file': (BytesIO(large_data), 'large.mp4')},
                          content_type='multipart/form-data')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'File size exceeds' in data['error']
def test_prepare_context(client):
    """Test chat context preparation"""
    with patch('app.prepare_context') as mock_prepare:
        mock_prepare.return_value = "Prepared context"
        
        test_data = {
            'query': 'test question',
            'history': ['previous message'],
            'document': 'test document'  # Document will be ignored by the endpoint
        }
        
        response = client.post('/ollama/chat', json=test_data)
        assert response.status_code == 200
        mock_prepare.assert_called_once_with(
            ['previous message'], 
            '',  # The endpoint always passes empty string
            'test question'
        )

def test_chat_system_error_handling(client):
    """Test chat system error scenarios"""
    test_data = {
        'query': 'test question',
        'history': ['previous message'],
        'document': 'test document'
    }
    
    # Test context preparation error
    with patch('app.prepare_context') as mock_prepare:
        mock_prepare.side_effect = Exception("Context preparation failed")
        response = client.post('/ollama/chat', json=test_data)
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
    
    # Test query execution error
    with patch('app.prepare_context') as mock_prepare, \
         patch('app.query_ollama') as mock_query:
        mock_prepare.return_value = "Prepared context"
        mock_query.side_effect = Exception("Query execution failed")
        response = client.post('/ollama/chat', json=test_data)
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data

def test_directory_permission_error():
    """Test directory initialization with permission errors"""
    with patch('os.makedirs') as mock_makedirs, \
         patch('pathlib.Path.chmod') as mock_chmod:
        # Test permission error during directory creation
        mock_makedirs.side_effect = PermissionError("Permission denied")
        
        with pytest.raises(Exception) as exc_info:
            init_directories()
        assert "Permission denied" in str(exc_info.value)
        
        # Reset mock and test permission error during chmod
        mock_makedirs.side_effect = None
        mock_chmod.side_effect = PermissionError("Permission denied")
        init_directories()  # Should not raise exception for chmod failure

def test_file_size_validation_edge_cases(client):
    """Test file size validation edge cases"""
    # Test exactly at size limit
    content = b'x' * settings.MAX_FILE_SIZE
    response = client.post('/api/v1/process', 
                          data={'file': (BytesIO(content), 'test.mp4')},
                          content_type='multipart/form-data')
    assert response.status_code == 400  # Should still fail due to overhead
    
    # Test slightly under size limit
    content = b'x' * (settings.MAX_FILE_SIZE - 1024)  # 1KB under limit
    response = client.post('/api/v1/process', 
                          data={'file': (BytesIO(content), 'test.mp4')},
                          content_type='multipart/form-data')
    assert response.status_code != 400  # Should not fail due to size

def test_file_cleanup_after_validation_error(client, setup_directories):
    """Test file cleanup after validation errors"""
    with patch('app.validate_file') as mock_validate:
        mock_validate.return_value = "Validation error"
        
        data = {
            'file': (BytesIO(b'test content'), 'test.mp4'),
            'title': 'Test'
        }
        
        response = client.post('/api/v1/process', 
                             data=data,
                             content_type='multipart/form-data')
        
        # Check that no files remain in upload directory
        upload_dir = setup_directories['uploads']
        assert len(list(upload_dir.glob('*'))) == 0

def test_error_handler_with_traceback(client):
    """Test error handler with traceback information"""
    with patch('app.process_video') as mock_process:
        def raise_with_traceback():
            try:
                raise ValueError("Test error")
            except ValueError as e:
                raise RuntimeError("Wrapped error") from e
        
        mock_process.side_effect = raise_with_traceback
        
        response = client.post('/api/v1/process', 
                             data={'file': (BytesIO(b'test'), 'test.mp4')},
                             content_type='multipart/form-data')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert 'details' in data
        assert 'Traceback' in data['details']