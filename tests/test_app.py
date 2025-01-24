import pytest
from unittest.mock import patch, MagicMock
import os
from io import BytesIO
from pathlib import Path
from faster_whisper import WhisperModel

from app import app, validate_file

@pytest.fixture
def mock_whisper_model():
    with patch('faster_whisper.WhisperModel') as mock_model:
        model_instance = MagicMock()
        segments = [
            MagicMock(text="Test segment 1"),
            MagicMock(text="Test segment 2")
        ]
        info = MagicMock(language="en", language_probability=0.98)
        model_instance.transcribe.return_value = (segments, info)
        mock_model.return_value = model_instance
        yield mock_model

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_transcribe_with_faster_whisper(mock_whisper_model, tmp_path):
    from transcribe.transcribe import transcribe
    
    # Create test audio file
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"test audio content")
    
    # Create output directory
    output_dir = tmp_path / "transcripts"
    output_dir.mkdir()
    
    # Run transcription
    elapsed_time, text, path = transcribe(str(audio_file), str(output_dir))
    
    # Verify model was called correctly
    mock_whisper_model.assert_called_once_with(
        model_size="large-v3",
        device="cuda",
        compute_type="float16"
    )
    
    # Verify output
    assert "Test segment 1" in text
    assert "Test segment 2" in text
    assert Path(path).exists()

def test_transcribe_empty_output(mock_whisper_model, tmp_path):
    from transcribe.transcribe import transcribe
    
    # Mock empty transcription
    model_instance = mock_whisper_model.return_value
    model_instance.transcribe.return_value = ([], MagicMock(language="en", language_probability=0.98))
    
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"test audio content")
    
    with pytest.raises(RuntimeError, match="Transcription produced empty output"):
        transcribe(str(audio_file), str(tmp_path))

def test_transcribe_file_not_found():
    from transcribe.transcribe import transcribe
    
    with pytest.raises(FileNotFoundError):
        transcribe("nonexistent.wav")

def test_process_video_with_faster_whisper(mock_whisper_model, tmp_path):
    from transcribe.processor import process_video
    
    # Create test video file
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"test video content")
    
    with patch('transcribe.get_video.process_local_video') as mock_process_video:
        mock_process_video.return_value = str(tmp_path / "test.wav")
        
        result = process_video(video_file, "Test Video")
        
        assert 'audio_path' in result
        assert 'transcript_path' in result
        assert 'summary_path' in result
        assert 'logseq_path' in result

def test_validate_file():
    class MockFile:
        def __init__(self, filename, content_length=None):
            self.filename = filename
            self.content_length = content_length

    assert validate_file(None) == "No file provided"
    assert validate_file(MockFile("", 1024)) == "No file selected"
    assert validate_file(MockFile("test.txt", 1024)) == "File type not allowed"
    assert validate_file(MockFile("test.mp4", 1024)) is None

def test_upload_endpoint(client, mock_whisper_model):
    with patch('transcribe.processor.process_video') as mock_process:
        mock_process.return_value = {
            'audio_path': Path('test_audio.wav'),
            'transcript_path': Path('test_transcript.txt'),
            'summary_path': Path('test_summary.txt'),
            'logseq_path': Path('test_logseq.md')
        }
        
        response = client.post(
            '/api/v1/process',
            data={
                'file': (BytesIO(b'test content'), 'test.mp4'),
                'title': 'Test Video'
            },
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert 'files' in data

def test_error_handling(client):
    # Test no file
    response = client.post('/api/v1/process')
    assert response.status_code == 400
    
    # Test invalid file type
    response = client.post(
        '/api/v1/process',
        data={'file': (BytesIO(b'test'), 'test.txt')},
        content_type='multipart/form-data'
    )
    assert response.status_code == 400

def test_large_file_handling(client):
    app.config['MAX_CONTENT_LENGTH'] = 100
    response = client.post(
        '/api/v1/process',
        data={'file': (BytesIO(b'x' * 200), 'test.mp4')},
        content_type='multipart/form-data'
    )
    assert response.status_code == 400
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # Reset to original