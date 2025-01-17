import pytest
import os
import sys
from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import app and its components
from app import app, validate_file, create_logseq_note, process_video, init_directories
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
        "logseq": temp_dir / "logseq"
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

def test_basic():
    """Basic test to verify testing setup"""
    assert True

def test_home_page(client):
    """Test the home page endpoint"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'<!DOCTYPE html>' in response.data

def test_status_endpoint(client):
    """Test the status endpoint"""
    response = client.get(f'{settings.API_PREFIX}/status')
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
    assert validate_file(large_file) == f"File size exceeds {settings.MAX_FILE_SIZE/(1024*1024)}MB limit"

    # Test invalid extension
    wrong_type = MockFile('test.txt', content_length=1024)
    assert validate_file(wrong_type) == "File type not allowed"

    # Test no extension
    no_ext = MockFile('testfile', content_length=1024)
    assert validate_file(no_ext) == "Invalid file format"

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

def test_logseq_note_io_error(temp_dir, monkeypatch):
    """Test IO error handling in Logseq note creation"""
    # Create a test summary file
    summary_file = temp_dir / "test_summary.txt"
    summary_file.write_text("Test content")
    
    # Counter to control which call to open raises the error
    call_count = 0
    original_open = open
    
    def mock_open(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # Let the first read succeed, fail on write
            raise IOError("Mock IO error")
        return original_open(*args, **kwargs)
        
    monkeypatch.setattr('builtins.open', mock_open)
    
    result = create_logseq_note(summary_file, "Test")
    assert result is None


def test_upload_no_file(client):
    """Test upload endpoint with no file"""
    response = client.post(f'{settings.API_PREFIX}/process')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == "No file selected"

def test_upload_empty_filename(client):
    """Test upload with empty filename"""
    data = {'file': (BytesIO(b''), '')}
    response = client.post(
        f'{settings.API_PREFIX}/process',
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
        f'{settings.API_PREFIX}/process',
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == "File type not allowed"

def test_upload_valid_file(client, setup_directories, mock_video_file, monkeypatch):
    """Test upload with valid video file"""
    result_files = {
        'audio_path': setup_directories['audio'] / 'test_audio.wav',
        'transcript_path': setup_directories['transcripts'] / 'test_transcript.txt',
        'summary_path': setup_directories['summaries'] / 'test_summary.txt',
        'logseq_path': setup_directories['logseq'] / 'test_note.md'
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
        f'{settings.API_PREFIX}/process',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert 'files' in data

def test_process_video_error_handling(client, setup_directories, mock_video_file, monkeypatch):
    """Test error handling in process_video function"""
    def mock_process_local_video(file_path):
        raise RuntimeError("Mock audio extraction error")
        
    monkeypatch.setattr('app.process_local_video', mock_process_local_video)
    
    data = {
        'file': (BytesIO(mock_video_file.content), mock_video_file.filename),
        'title': 'Test Video'
    }
    
    response = client.post(
        f'{settings.API_PREFIX}/process',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert 'Mock audio extraction error' in str(data['error'])


def test_process_video_invalid_paths(client, setup_directories, mock_video_file, monkeypatch):
    """Test handling of invalid paths in process_video"""
    # Mock process_video to return invalid paths
    def mock_process_local_video(file_path):
        return str(Path('nonexistent.wav'))

    monkeypatch.setattr('app.process_local_video', mock_process_local_video)

    # Mock transcribe to simulate processing
    def mock_transcribe(audio_path):
        return 1, "test", str(Path('nonexistent.txt'))

    monkeypatch.setattr('app.transcribe', mock_transcribe)

    data = {
        'file': (BytesIO(mock_video_file.content), mock_video_file.filename),
        'title': 'Test Video'
    }

    response = client.post(
        f'{settings.API_PREFIX}/process',
        data=data,
        content_type='multipart/form-data'
    )

    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert 'No such file or directory' in str(data['error'])


def test_large_file_upload(client):
    """Test upload with file exceeding size limit"""
    app.config['MAX_CONTENT_LENGTH'] = 1024  # Set a small limit for testing
    large_content = b'x' * 2048  # Content larger than limit
    data = {
        'file': (BytesIO(large_content), 'large.mp4')
    }
    response = client.post(
        f'{settings.API_PREFIX}/process',
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "File size exceeds" in data['error']
    app.config['MAX_CONTENT_LENGTH'] = settings.MAX_FILE_SIZE  # Restore original limit

def test_concurrent_requests(client):
    """Test handling multiple concurrent requests"""
    import threading
    import queue
    
    results = queue.Queue()
    
    def make_request():
        response = client.get(f'{settings.API_PREFIX}/status')
        results.put(response.status_code)
    
    # Create and run multiple threads
    threads = [threading.Thread(target=make_request) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    
    # Check all responses
    while not results.empty():
        assert results.get() == 200

def test_upload_cleanup(client, setup_directories, mock_video_file, monkeypatch):
    """Test that uploaded files are cleaned up"""
    # Mock process_video to return valid paths
    def mock_process(file_path, title):
        return {
            'audio_path': setup_directories['audio'] / 'test_audio.wav',
            'transcript_path': setup_directories['transcripts'] / 'test_transcript.txt',
            'summary_path': setup_directories['summaries'] / 'test_summary.txt',
            'logseq_path': setup_directories['logseq'] / 'test_note.md'
        }
    monkeypatch.setattr('app.process_video', mock_process)

    data = {
        'file': (BytesIO(mock_video_file.content), mock_video_file.filename),
        'title': 'Test Video'
    }
    response = client.post(
        f'{settings.API_PREFIX}/process',
        data=data,
        content_type='multipart/form-data'
    )
    
    # Check that uploaded file was cleaned up
    assert len(list(settings.OUTPUT_DIRS['uploads'].iterdir())) == 0

def test_process_video_cleanup_error(client, setup_directories, mock_video_file, monkeypatch):
    """Test error handling during file cleanup"""
    def mock_unlink(*args):
        raise OSError("Mock cleanup error")
        
    # Mock the unlink method
    monkeypatch.setattr(Path, 'unlink', mock_unlink)
    
    # Mock process_video to avoid actual processing
    def mock_process(file_path, title):
        return {
            'audio_path': setup_directories['audio'] / 'test_audio.wav',
            'transcript_path': setup_directories['transcripts'] / 'test_transcript.txt',
            'summary_path': setup_directories['summaries'] / 'test_summary.txt',
            'logseq_path': setup_directories['logseq'] / 'test_note.md'
        }
    monkeypatch.setattr('app.process_video', mock_process)
    
    data = {
        'file': (BytesIO(mock_video_file.content), mock_video_file.filename),
        'title': 'Test Video'
    }
    
    response = client.post(
        f'{settings.API_PREFIX}/process',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 200  # The request should still succeed even if cleanup fails

@app.route('/test-error')
def trigger_error():
    """Test route to trigger a 500 error"""
    raise ValueError("Test error")

def test_error_handler(client):
    """Test global error handler"""
    # Test 404 error
    response = client.get('/nonexistent')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'Not Found'
    
    # Test 500 error
    response = client.get('/test-error')
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'Internal Server Error'
    assert 'message' in data
    assert 'details' in data


def test_missing_directory_creation(temp_dir, client, monkeypatch):
    """Test automatic creation of missing directories"""
    import app as app_module  # Import the module itself
    
    # Store original directories
    original_dirs = settings.OUTPUT_DIRS.copy()
    
    try:
        # Update settings to use temp directory
        test_dirs = {
            "uploads": temp_dir / "uploads",
            "audio": temp_dir / "audio",
            "transcripts": temp_dir / "transcripts",
            "summaries": temp_dir / "summaries",
            "logseq": temp_dir / "logseq"
        }
        
        # Update settings
        settings.OUTPUT_DIRS = test_dirs
        
        # Remove all directories if they exist
        for directory in test_dirs.values():
            if directory.exists():
                shutil.rmtree(directory)
                
        # Run initialization
        init_directories()
            
        # Check all directories exist
        for directory in test_dirs.values():
            assert directory.exists()
            assert directory.is_dir()
    
    finally:
        # Restore original directories
        settings.OUTPUT_DIRS = original_dirs

def test_init_directories_error(monkeypatch):
    """Test error handling in directory initialization"""
    def mock_makedirs(*args, **kwargs):
        raise OSError("Mock directory creation error")
        
    monkeypatch.setattr(os, 'makedirs', mock_makedirs)
    
    with pytest.raises(OSError):
        init_directories()

if __name__ == '__main__':
    pytest.main(['-v', __file__])