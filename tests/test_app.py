import pytest
import os
import sys
from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import app and its components
from app import app, validate_file, create_logseq_note
from config import settings
from admin.math_analytics import MathLectureAnalyzer
from admin.lecture_stats import LectureStatsTracker

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
def mock_stats_file(temp_dir):
    """Create a mock stats file for testing"""
    stats = {
        "metadata": {
            "title": "test_video",
            "processing_time": 107,
            "timestamp": datetime.now().isoformat(),
            "source_file": "test_video.mp4"
        },
        "analysis": {
            "word_count": 1000,
            "chunk_count": 2,
            "summary_count": 1,
            "topics": {
                "core_topics": ["Mathematics", "Linear Algebra"],
                "dependencies": ["Topic A -> Topic B"],
                "theoretical_links": ["Link 1"]
            },
            "concepts": {
                "key_concepts": ["Matrices", "Vectors"],
                "relationships": ["Relationship 1"],
                "prerequisites": ["Prereq 1"]
            },
            "learning_objectives": [
                "Understand matrices",
                "Apply vector operations"
            ],
            "complexity_analysis": {
                "total_score": 5.0,
                "metrics": {
                    "term_density": 5.0,
                    "concept_density": 5.0,
                    "abstraction_level": 5.0
                }
            }
        }
    }
    
    stats_file = temp_dir / "test_video_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f)
    return stats_file

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

    # Create directories
    for directory in test_dirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    # Store original directories
    original_dirs = settings.OUTPUT_DIRS.copy()
    settings.OUTPUT_DIRS.update(test_dirs)

    yield test_dirs

    # Restore original directories
    settings.OUTPUT_DIRS = original_dirs

def test_admin_dashboard_access(client):
    """Test access to admin dashboard"""
    response = client.get('/admin/')
    assert response.status_code == 200
    assert b'Admin Analytics Dashboard' in response.data

def test_admin_api_stats(client, setup_directories, mock_stats_file):
    """Test admin stats API endpoint"""
    response = client.get('/admin/api/stats')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'word_counts' in data
    assert 'total_documents' in data
    assert 'processing_stats' in data

def test_lecture_stats_tracking(setup_directories, mock_stats_file):
    """Test lecture statistics tracking"""
    stats_tracker = LectureStatsTracker(str(setup_directories["stats"]))
    lecture_stats = stats_tracker.get_lecture_stats("test_video")
    
    assert lecture_stats['metadata']['title'] == "test_video"
    assert lecture_stats['analysis']['word_count'] == 1000
    assert 'topics' in lecture_stats['analysis']
    assert 'concepts' in lecture_stats['analysis']

def test_math_lecture_analyzer():
    """Test math content analyzer"""
    analyzer = MathLectureAnalyzer()
    content = "Let's discuss matrices and vectors in linear algebra."
    
    # Test topic analysis
    topics = analyzer.analyze_topic_relationships(content)
    assert isinstance(topics, dict)
    assert 'core_topics' in topics
    
    # Test concept mapping
    concepts = analyzer.generate_concept_map(content)
    assert isinstance(concepts, dict)
    assert 'concepts' in concepts
    
    # Test complexity analysis
    complexity = analyzer.analyze_complexity()
    assert isinstance(complexity, list)
    assert len(complexity) > 0

def test_admin_api_lecture_stats(client, setup_directories, mock_stats_file):
    """Test individual lecture stats API endpoint"""
    response = client.get('/admin/api/lecture/test_video')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['metadata']['title'] == "test_video"
    assert 'analysis' in data

def test_admin_api_invalid_lecture(client):
    """Test API response for non-existent lecture"""
    response = client.get('/admin/api/lecture/nonexistent')
    assert response.status_code == 404

def test_stats_file_creation(setup_directories, mock_video_file, monkeypatch):
    """Test stats file creation during video processing"""
    def mock_process_video(*args):
        return {'audio_path': 'test.wav', 'stats_path': 'test_stats.json'}
    monkeypatch.setattr('app.process_video', mock_process_video)
    
    data = {
        'file': (BytesIO(mock_video_file.content), mock_video_file.filename),
        'title': 'Test Video'
    }
    
    with app.test_client() as client:
        response = client.post('/api/v1/process', data=data)
        assert response.status_code == 200
        assert 'stats_path' in json.loads(response.data)['files']

def test_missing_stats_directory(temp_dir):
    """Test handling of missing stats directory"""
    stats_dir = temp_dir / "missing_stats"
    stats_tracker = LectureStatsTracker(str(stats_dir))
    assert stats_tracker.get_all_stats() == {}

def test_malformed_stats_file(setup_directories):
    """Test handling of malformed stats file"""
    stats_file = setup_directories["stats"] / "malformed_stats.json"
    with open(stats_file, 'w') as f:
        f.write("invalid json")
        
    stats_tracker = LectureStatsTracker(str(setup_directories["stats"]))
    stats = stats_tracker.get_lecture_stats("malformed_stats")
    assert stats == {}

def test_admin_api_stats_empty(client, setup_directories):
    """Test stats API with no data"""
    response = client.get('/admin/api/stats')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['word_counts']['total'] == 0
    assert data['total_documents'] == 0

def test_admin_api_stats_error(client, monkeypatch):
    """Test stats API error handling"""
    def mock_get_stats_data():
        raise Exception("Mock error")
    monkeypatch.setattr('admin.routes.get_stats_data', mock_get_stats_data)
    
    response = client.get('/admin/api/stats')
    assert response.status_code == 500
    assert 'error' in json.loads(response.data)

def test_concurrent_stats_access(client, setup_directories, mock_stats_file):
    """Test concurrent access to stats endpoint"""
    import threading
    import queue
    
    results = queue.Queue()
    
    def make_request():
        response = client.get('/admin/api/stats')
        results.put(response.status_code)
    
    threads = [threading.Thread(target=make_request) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    
    while not results.empty():
        assert results.get() == 200

if __name__ == '__main__':
    pytest.main(['-v', __file__])