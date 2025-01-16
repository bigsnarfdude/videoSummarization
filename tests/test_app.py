import pytest
import os
import sys
from io import BytesIO
import json

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import app and its components
from app import app, UPLOAD_FOLDER, SUMMARIES_DIR, LOGSEQ_DIR, allowed_file, create_logseq_note

@pytest.fixture
def client():
    """Create a test client for the app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_video_file():
    """Create a mock video file for testing."""
    return BytesIO(b'mock video content'), 'test_video.mp4'

@pytest.fixture
def setup_directories():
    """Ensure required directories exist."""
    for directory in [UPLOAD_FOLDER, SUMMARIES_DIR, LOGSEQ_DIR]:
        os.makedirs(directory, exist_ok=True)
    yield
    # Cleanup after tests
    for directory in [UPLOAD_FOLDER, SUMMARIES_DIR, LOGSEQ_DIR]:
        for file in os.listdir(directory):
            os.remove(os.path.join(directory, file))

# Basic Tests
def test_basic():
    """Verify testing setup is working."""
    assert True

# Endpoint Tests
def test_home_page(client):
    """Test the home page endpoint."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'<!DOCTYPE html>' in response.data

def test_status_endpoint(client):
    """Test the status endpoint."""
    response = client.get('/api/status')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'running'

# File Upload Tests
def test_upload_no_file(client):
    """Test upload endpoint with no file."""
    response = client.post('/api/process')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'No file provided'

def test_upload_empty_filename(client):
    """Test upload with empty filename."""
    response = client.post('/api/process', data={
        'file': (BytesIO(b''), '')
    })
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'No file selected'

def test_upload_invalid_file_type(client):
    """Test upload with invalid file type."""
    data = {
        'file': (BytesIO(b'test content'), 'test.txt')
    }
    response = client.post(
        '/api/process',
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'File type not allowed'

def test_upload_valid_file(client, mock_video_file, setup_directories):
    """Test upload with valid video file."""
    file_content, filename = mock_video_file
    data = {
        'file': (file_content, filename),
        'title': 'Test Video'
    }
    response = client.post(
        '/api/process',
        data=data,
        content_type='multipart/form-data'
    )
    
    # Note: This might return 500 if actual processing fails
    # We're mainly testing the upload part here
    assert response.status_code in [200, 500]
    if response.status_code == 200:
        data = json.loads(response.data)
        assert 'status' in data
        assert 'files' in data
    else:
        data = json.loads(response.data)
        assert 'error' in data

# Utility Function Tests
def test_allowed_file():
    """Test the allowed_file function."""
    # Test valid extensions
    assert allowed_file('video.mp4') is True
    assert allowed_file('video.avi') is True
    assert allowed_file('video.mov') is True
    assert allowed_file('video.mkv') is True
    
    # Test invalid extensions
    assert allowed_file('document.pdf') is False
    assert allowed_file('video.txt') is False
    assert allowed_file('video') is False
    assert allowed_file('.mp4') is False

def test_create_logseq_note(tmp_path):
    """Test logseq note creation."""
    # Create a temporary summary file
    summary_file = tmp_path / "test_summary.txt"
    summary_content = "Test summary content\nLine 2"
    summary_file.write_text(summary_content)
    
    # Create the note
    title = "Test Video"
    logseq_path = create_logseq_note(str(summary_file), title)
    
    # Verify the note was created
    assert logseq_path is not None
    assert os.path.exists(logseq_path)
    
    # Check content
    with open(logseq_path, 'r') as f:
        content = f.read()
        assert f"- summarized [[{title}]]" in content
        assert "- [[summary]]" in content
        assert "Test summary content" in content

# Error Handling Tests
def test_process_video_invalid_path(client, setup_directories):
    """Test processing with invalid video path."""
    data = {
        'file': (BytesIO(b'test'), 'nonexistent.mp4'),
        'title': 'Test'
    }
    response = client.post(
        '/api/process',
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code in [400, 500]

# Concurrent Request Tests
def test_concurrent_requests(client):
    """Test handling multiple concurrent requests."""
    import threading
    import queue
    
    results = queue.Queue()
    
    def make_request():
        response = client.get('/api/status')
        results.put(response.status_code)
    
    # Create multiple threads
    threads = [threading.Thread(target=make_request) for _ in range(10)]
    
    # Start all threads
    for thread in threads:
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Check all responses
    while not results.empty():
        assert results.get() == 200

# Resource Cleanup Tests
def test_upload_cleanup(client, mock_video_file, setup_directories):
    """Test that uploaded files are cleaned up."""
    file_content, filename = mock_video_file
    data = {
        'file': (file_content, filename),
        'title': 'Test Video'
    }
    client.post(
        '/api/process',
        data=data,
        content_type='multipart/form-data'
    )
    
    # Check that no files remain in upload folder
    assert len(os.listdir(UPLOAD_FOLDER)) == 0

if __name__ == '__main__':
    pytest.main(['-v', __file__])