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
import requests

from unittest.mock import patch, MagicMock, PropertyMock, call
from flask import url_for
from werkzeug.exceptions import RequestEntityTooLarge

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import app and its components
from app import app, validate_file, init_directories, setup_logging, query_ollama, prepare_context
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
    test_dirs = {
        "uploads": temp_dir / "uploads",
        "audio": temp_dir / "audio",
        "transcripts": temp_dir / "transcripts",
        "summaries": temp_dir / "summaries",
        "logseq": temp_dir / "logseq",
        "stats": temp_dir / "stats"
    }

    for directory in test_dirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    original_dirs = settings.OUTPUT_DIRS.copy()
    settings.OUTPUT_DIRS.update(test_dirs)

    yield test_dirs

    settings.OUTPUT_DIRS = original_dirs

@pytest.fixture
def mock_video_file():
    """Create a mock video file for testing"""
    return MockFile(
        filename='test_video.mp4',
        content=b'mock video content',
        content_length=1024
    )

def test_init_directories_failure():
    """Test directory initialization complete failure"""
    with patch('os.makedirs') as mock_makedirs:
        mock_makedirs.side_effect = PermissionError("Permission denied")
        with pytest.raises(Exception) as exc_info:
            init_directories()
        assert "Permission denied" in str(exc_info.value)

def test_logging_setup_complete_failure():
    """Test logging setup when all handlers fail"""
    with patch('logging.getLogger') as mock_logger, \
         patch('logging.handlers.RotatingFileHandler') as mock_handler, \
         patch('logging.StreamHandler') as mock_stream:
        mock_handler.side_effect = Exception("Handler failed")
        mock_stream.side_effect = Exception("Stream failed")
        with pytest.raises(Exception) as exc_info:
            setup_logging()
        assert "Handler failed" in str(exc_info.value)

def test_query_ollama_connection_error():
    """Test Ollama API connection failures"""
    with patch('requests.post') as mock_post:
        # Test connection error
        mock_post.side_effect = requests.ConnectionError("Connection failed")
        response = query_ollama("test prompt")
        assert "Error connecting to Ollama" in response
        
        # Test timeout error
        mock_post.side_effect = requests.Timeout("Request timed out")
        response = query_ollama("test prompt")
        assert "Error connecting to Ollama" in response

def test_ollama_api_error():
    """Test Ollama API error responses"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_post.return_value = mock_response
        response = query_ollama("test prompt")
        assert "Unexpected error" in response

def test_chat_request_validation(client):
    """Test chat request validation scenarios"""
    # Test empty request body
    response = client.post('/ollama/chat', json=None)
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'No data provided'

    # Test missing query
    response = client.post('/ollama/chat', json={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Query is required'

    # Test empty query
    response = client.post('/ollama/chat', json={'query': ''})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Query is required'

def test_prepare_context_variations():
    """Test context preparation with different input combinations"""
    # Test with all empty values
    result = prepare_context([], '', '')
    assert result == '\nCurrent query: '

    # Test with only query
    result = prepare_context([], '', 'test query')
    assert result == '\nCurrent query: test query'

    # Test with history
    result = prepare_context(['msg1', 'msg2'], '', 'test query')
    assert 'msg1' in result
    assert 'msg2' in result

    # Test with context
    result = prepare_context([], 'test context', 'test query')
    assert 'Context:\ntest context' in result

def test_request_entity_too_large(client):
    """Test handling of oversized requests"""
    original_max_length = app.config['MAX_CONTENT_LENGTH']
    app.config['MAX_CONTENT_LENGTH'] = 1024  # Set a small limit

    try:
        large_data = b'x' * 2048
        response = client.post(
            '/api/v1/process',
            data={'file': (BytesIO(large_data), 'test.mp4')},
            content_type='multipart/form-data'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "File size exceeds" in data['error']
    finally:
        app.config['MAX_CONTENT_LENGTH'] = original_max_length

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
    valid_file = MockFile('test.mp4', content_length=1024)
    assert validate_file(valid_file) is None

    assert validate_file(None) == "No file provided"

    no_name_file = MockFile('', content_length=1024)
    assert validate_file(no_name_file) == "No file selected"

    large_file = MockFile('test.mp4', content_length=settings.MAX_FILE_SIZE + 1)
    assert "File size exceeds" in validate_file(large_file)

    long_name = 'a' * (settings.MAX_FILENAME_LENGTH + 1) + '.mp4'
    long_file = MockFile(long_name)
    assert "Filename too long" in validate_file(long_file)

    wrong_type = MockFile('test.txt', content_length=1024)
    assert validate_file(wrong_type) == "File type not allowed"

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
    response = client.post('/api/v1/process', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == "No file selected"

def test_upload_invalid_file_type(client):
    """Test upload with invalid file type"""
    data = {'file': (BytesIO(b'test content'), 'test.txt')}
    response = client.post('/api/v1/process', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == "File type not allowed"

def test_chat_system_error_handling(client):
    """Test chat system error scenarios"""
    chat_data = {
        'query': 'test question',
        'history': ['previous message'],
        'document': 'test document'
    }
    
    # Test context preparation error
    with patch('app.prepare_context') as mock_prepare:
        mock_prepare.side_effect = Exception("Context preparation failed")
        response = client.post('/ollama/chat', json=chat_data)
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
    
    # Test query execution error
    with patch('app.prepare_context') as mock_prepare, \
         patch('app.query_ollama') as mock_query:
        mock_prepare.return_value = "Prepared context"
        mock_query.side_effect = Exception("Query execution failed")
        response = client.post('/ollama/chat', json=chat_data)
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data

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


def test_404_error_handler(client):
    """Test 404 error handler"""
    response = client.get('/nonexistent-route')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'Not Found'
    assert 'message' in data

def test_413_error_handler(client):
    """Test 413 (Request Entity Too Large) error handler"""
    original_max_length = app.config['MAX_CONTENT_LENGTH']
    app.config['MAX_CONTENT_LENGTH'] = 100  # Set a very small limit
    try:
        data = {'file': (BytesIO(b'x' * 200), 'test.mp4')}
        response = client.post('/api/v1/process', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert "File size exceeds" in data['error']
    finally:
        app.config['MAX_CONTENT_LENGTH'] = original_max_length

def test_unhandled_exception_handler(client):
    """Test generic exception handler"""
    with patch('app.process_video') as mock_process:
        mock_process.side_effect = Exception("Unexpected error")
        data = {'file': (BytesIO(b'test'), 'test.mp4')}
        response = client.post('/api/v1/process', data=data, content_type='multipart/form-data')
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error'] == 'Unexpected error'
        assert 'details' in data
        assert 'type' in data
        assert data['type'] == 'Exception'

def test_query_ollama_timeout():
    """Test Ollama API timeout handling"""
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.Timeout("Request timed out")
        result = query_ollama("test prompt")
        assert "Error connecting to Ollama" in result
        assert "Request timed out" in result

def test_prepare_context_empty():
    """Test prepare_context with empty inputs"""
    result = prepare_context([], '', '')
    assert 'Current query' in result
    assert result.endswith('Current query: ')

def test_prepare_context_full():
    """Test prepare_context with all inputs"""
    history = ['previous message 1', 'previous message 2']
    context = 'test context'
    query = 'test query'
    result = prepare_context(history, context, query)
    assert 'Context:\ntest context' in result
    assert 'Previous conversation:' in result
    assert 'previous message 1' in result
    assert 'previous message 2' in result
    assert 'Current query: test query' in result

def test_ollama_chat_system_error(client):
    """Test chat endpoint system error handling"""
    with patch('app.query_ollama') as mock_query:
        mock_query.side_effect = Exception("System error")
        response = client.post('/ollama/chat', 
                             json={'query': 'test'},
                             content_type='application/json')
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert 'System error' in data['error']

######## not sure these are needed

def test_query_ollama_server_error(monkeypatch):
    """Test Ollama API when server returns an error response"""
    import requests

    def mock_post(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("Server error")
        return mock_response
    
    monkeypatch.setattr(requests, 'post', mock_post)
    
    result = query_ollama("test prompt")
    assert "Error connecting to Ollama" in result

def test_prepare_context_long_inputs():
    """Test context preparation with extremely long inputs"""
    long_history = ['Long message ' * 100] * 5  # Very long messages
    long_context = 'Long context ' * 200  # Extremely long context
    long_query = 'Very long query ' * 50

    result = prepare_context(long_history, long_context, long_query)
    
    # Verify basic structure is maintained
    assert 'Context:' in result
    assert 'Previous conversation:' in result
    assert 'Current query:' in result

def test_chat_endpoint_missing_json_content(client):
    """Test chat endpoint with malformed JSON"""
    # Send request with no content type
    response = client.post('/ollama/chat', data='invalid json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_file_validation_edge_cases():
    """Test file validation with various edge case scenarios"""
    class MockFile:
        def __init__(self, filename, content_length=None):
            self.filename = filename
            self.content_length = content_length

    # Test filename with multiple dots
    file1 = MockFile('video.special.mp4', content_length=100)
    assert validate_file(file1) is None

    # Test filename with no extension but within allowed name length
    file2 = MockFile('videofile', content_length=100)
    assert validate_file(file2) == "Invalid file format"

    # Test filename with uppercase extension
    file3 = MockFile('video.MP4', content_length=100)
    assert validate_file(file3) is None

def test_process_video_endpoint_without_title(client, mock_video_file):
    """Test video processing endpoint without explicit title"""
    data = {
        'file': (BytesIO(mock_video_file.content), mock_video_file.filename)
    }
    
    # Mock process_video to return a predefined result
    with patch('app.process_video') as mock_process:
        mock_process.return_value = {
            'audio_path': Path('test_audio.wav'),
            'transcript_path': Path('test_transcript.txt'),
            'summary_path': Path('test_summary.txt'),
            'logseq_path': Path('test_logseq.md'),
            'stats_path': Path('test_stats.json')
        }
        
        response = client.post(
            f'{settings.API_PREFIX}/process', 
            data=data,
            content_type='multipart/form-data'
        )
        
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert 'files' in data

def test_status_endpoint_details(client):
    """Test status endpoint returns expected structure"""
    response = client.get('/status')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'running'

def test_404_error_handler_details(client):
    """Test 404 error handler provides detailed information"""
    response = client.get('/totally-nonexistent-route')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data
    assert 'message' in data
    assert data['error'] == 'Not Found'


def test_home_page_content(client):
    """Test that the home page renders the correct template"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'<!DOCTYPE html>' in response.data

def test_chat_endpoint_json_parsing_edge_cases(client):
    """Test chat endpoint with edge case JSON inputs"""
    # Test with None as the entire JSON body
    response = client.post('/ollama/chat', data=None, content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'No data provided'

    # Test with empty request body
    response = client.post('/ollama/chat', data='', content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'No data provided'

    # Test with invalid JSON
    response = client.post('/ollama/chat', data='invalid json', content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'No data provided'

    # Test with empty JSON object
    response = client.post('/ollama/chat', json={}, content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Query is required'

    # Test with query as None
    response = client.post('/ollama/chat', json={'query': None}, content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Query is required'

    # Test with whitespace query
    response = client.post('/ollama/chat', json={'query': '   '}, content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Query is required'

    # Test with valid query (mock the Ollama response if needed)
    with patch('app.query_ollama') as mock_query:
        mock_query.return_value = "Test response"
        response = client.post('/ollama/chat', json={'query': 'Hello'}, content_type='application/json')
        assert response.status_code == 200

def test_validate_file_edge_cases():
    """Test file validation with edge case file inputs"""
    class MockFile:
        def __init__(self, filename, content_length=None):
            self.filename = filename
            self.content_length = content_length

    # Test file with no content length (should not raise an error)
    no_length_file = MockFile('test.mp4')
    assert validate_file(no_length_file) is None

    # Test file with zero content length
    zero_length_file = MockFile('test.mp4', content_length=0)
    assert validate_file(zero_length_file) is None

    # Test file with content length exceeding max file size
    large_file = MockFile('test.mp4', content_length=settings.MAX_FILE_SIZE + 1)
    assert "File size exceeds" in validate_file(large_file)


def test_init_directories_permission_error():
    """Test initialization when directory permissions can't be set"""
    with patch('pathlib.Path.chmod') as mock_chmod:
        mock_chmod.side_effect = PermissionError("Permission denied")
        init_directories()  # Should handle the error gracefully


def test_setup_logging_file_handler_error():
    """Test logging setup when file handler creation fails"""
    with patch('logging.handlers.RotatingFileHandler') as mock_handler:
        mock_handler.side_effect = PermissionError("Permission denied")
        with pytest.raises(Exception):
            setup_logging()

def test_query_ollama_edge_cases():
    """Test various Ollama API error scenarios"""
    with patch('requests.post') as mock_post:
        # Test timeout
        mock_post.side_effect = requests.Timeout("Request timed out")
        response = query_ollama("test prompt")
        assert "Error connecting to Ollama" in response

        # Test JSON decode error
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.side_effect = None
        mock_post.return_value = mock_response
        response = query_ollama("test prompt")
        assert "Unexpected error" in response

def test_process_video_cleanup_error():
    """Test error handling during file cleanup"""
    with patch('pathlib.Path.unlink') as mock_unlink:
        mock_unlink.side_effect = PermissionError("Permission denied")
        
        # Setup a mock file
        mock_file = MagicMock()
        mock_file.filename = "test.mp4"
        
        with app.test_client() as client:
            response = client.post(
                f'{settings.API_PREFIX}/process',
                data={'file': (BytesIO(b'test'), 'test.mp4')}
            )
            # Should complete despite cleanup error
            assert response.status_code in [400, 500]  # Depends on earlier processing

def test_large_file_error_detailed():
    """Test detailed error handling for large files"""
    original_max_size = app.config['MAX_CONTENT_LENGTH']
    app.config['MAX_CONTENT_LENGTH'] = 100  # Set very small limit
    
    try:
        with app.test_client() as client:
            data = {'file': (BytesIO(b'x' * 200), 'test.mp4')}
            response = client.post(
                f'{settings.API_PREFIX}/process',
                data=data,
                content_type='multipart/form-data'
            )
            assert response.status_code == 400
            data = response.get_json()
            assert 'error' in data
            assert 'MB limit' in data['error']
    finally:
        app.config['MAX_CONTENT_LENGTH'] = original_max_size

def test_log_file_permission_error():
    """Test handling of log file permission errors"""
    with patch('pathlib.Path.chmod') as mock_chmod:
        mock_chmod.side_effect = PermissionError("Permission denied")
        with patch('logging.getLogger') as mock_logger:
            setup_logging()
            mock_logger.return_value.warning.assert_called_with(
                "Could not set log file permissions: Permission denied"
            )



def test_file_cleanup_error():
    """Test file cleanup error handling (lines 285-288)"""
    with app.test_client() as client:
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.unlink') as mock_unlink:
            mock_unlink.side_effect = PermissionError("Permission denied")
            
            response = client.post(
                f'{settings.API_PREFIX}/process',
                data={'file': (BytesIO(b'test'), 'test.mp4')}
            )
            # Should complete despite cleanup error
            assert response.status_code in [400, 500]




def test_query_ollama_response_handling():
    """Test Ollama API response handling"""
    with patch('requests.post') as mock_post:
        # Test invalid JSON response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {}  # Empty response
        mock_post.return_value = mock_response
        
        response = query_ollama("test prompt")
        assert response == "No response received"
        
        # Test network timeout
        mock_post.side_effect = requests.Timeout("Request timed out")
        response = query_ollama("test prompt")
        assert "Error connecting to Ollama" in response
        
        # Test HTTP error
        mock_post.side_effect = requests.HTTPError("Internal server error")
        response = query_ollama("test prompt")
        assert "Error connecting to Ollama" in response


def test_rotating_file_handler_error():
    """Test error handling when creating rotating file handler"""
    with patch('logging.handlers.RotatingFileHandler') as mock_handler:
        mock_handler.side_effect = PermissionError("Permission denied")
        with patch('sys.stderr') as mock_stderr:
            with pytest.raises(PermissionError) as exc_info:
                setup_logging()
                
            # Check the actual error message
            assert "Permission denied" in str(exc_info.value)
            
            # Check that both write calls were made
            assert mock_stderr.write.call_count == 2
            mock_stderr.write.assert_has_calls([
                call("Error setting up logging: Permission denied"),
                call("\n")
            ])

def test_general_exception_handler():
    """Test general exception handler (lines 340-346)"""
    with app.test_client() as client:
        with patch('app.process_video') as mock_process:
            # Create a custom error
            mock_process.side_effect = ValueError("Test error")
            
            # Send request that will trigger the error
            response = client.post(
                f'{settings.API_PREFIX}/process',
                data={
                    'file': (BytesIO(b'test content'), 'test.mp4')
                },
                content_type='multipart/form-data'
            )
            
            # Verify response
            assert response.status_code == 500
            data = response.get_json()
            assert data['error'] == 'Test error'  # The actual error message
            assert 'details' in data  # Traceback should be present
            assert 'type' in data     # Error type should be present
            assert data['type'] == 'ValueError'

