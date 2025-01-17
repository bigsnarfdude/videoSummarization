# LLM Based Video Processing Service

A Flask-based web application for transcribing and summarizing video content. The service extracts audio from videos, performs transcription using Whisper.cpp, and generates summaries using MLX Phi-4.

## Features

- Web interface with drag-and-drop video upload
- REST API for programmatic access
- Video to audio conversion
- Speech-to-text transcription
- Text summarization
- Logseq-compatible note generation
- Comprehensive logging system
- Support for MP4, AVI, MOV, and MKV formats

## Requirements

### Core Dependencies
- Python 3.7+
- FFmpeg
- Whisper.cpp
- MLX

### Python Packages
- Flask
- Pydantic
- MLX
- MLX-LM
- Spacy
- Additional dependencies in `requirements.txt`

## Installation

1. Clone the repository:
   ```bash
   git clone <your-repository-url>
   cd video-processing-service
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Unix/macOS
   # OR
   .venv\Scripts\activate     # Windows
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Spacy language model:
   ```bash
   python -m spacy download en_core_web_sm
   ```

5. Install external dependencies:

   **FFmpeg:**
   - macOS: `brew install ffmpeg`
   - Ubuntu: `sudo apt-get install ffmpeg`
   - Windows: Download from [ffmpeg.org](https://ffmpeg.org/)

   **Whisper.cpp:**
   - Follow installation instructions at [Whisper.cpp GitHub](https://github.com/ggerganov/whisper.cpp)
   - Download and place the model file in your preferred location

   **MLX:**
   - Follow installation instructions for your platform

6. Create required directories:
   ```bash
   mkdir -p files/{uploads,audio,transcripts,summaries,logseq} logs
   ```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Update the following settings in `.env`:
   ```
   APP_ENV=development
   SECRET_KEY=your-secret-key
   WHISPER_PATH=/path/to/whisper/executable
   WHISPER_MODEL_PATH=/path/to/whisper/model
   ```

3. Additional configuration options are available in `config.py`:
   - File size limits
   - Allowed file types
   - Processing settings
   - Directory paths
   - Logging configuration

## Usage

### Starting the Server

1. Development mode:
   ```bash
   python app.py
   ```
   The server will start at `http://localhost:5000`

2. Production mode:
   ```bash
   export APP_ENV=production
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

### Web Interface

1. Open `http://localhost:5000` in your browser
2. Upload a video using drag-and-drop or file selection
3. Wait for processing to complete
4. Access generated files from the results panel

### REST API

The service provides a RESTful API for programmatic access:

#### Process Video
```bash
curl -X POST \
  -F "file=@/path/to/video.mp4" \
  -F "title=Video Title" \
  http://localhost:5000/api/v1/process
```

Response:
```json
{
    "status": "success",
    "files": {
        "audio": "video_file.wav",
        "transcript": "video_file.txt",
        "summary": "video_file_summary.txt",
        "logseq": "video_file.md"
    }
}
```

#### Check Status
```bash
curl http://localhost:5000/api/v1/status
```

### Output Files

The service generates several files for each processed video:

1. **Audio** (`files/audio/*.wav`)
   - Extracted audio in WAV format
   - 16kHz, mono, 16-bit PCM

2. **Transcript** (`files/transcripts/*.txt`)
   - Raw text transcription from Whisper

3. **Summary** (`files/summaries/*.txt`)
   - Generated summary from MLX Phi-4

4. **Logseq Note** (`files/logseq/*.md`)
   - Formatted note ready for Logseq import

## Development

### Project Structure
```
.
├── app.py              # Flask application
├── config.py           # Configuration settings
├── main.py            # CLI interface
├── requirements.txt   # Python dependencies
├── static/           # Static assets
│   └── js/
│       └── VideoProcessor.js
├── templates/        # HTML templates
│   └── index.html
├── tests/           # Test suite
└── transcribe/      # Core processing modules
```

### Running Tests
```bash
pytest
```

### Logging

Logs are stored in the `logs` directory:
- `app.log`: Application logs
- `api.log`: API request logs

## Troubleshooting

### Common Issues

1. **File Upload Errors**
   - Verify file format is supported
   - Check file size limits
   - Ensure upload directory is writable

2. **Processing Errors**
   - Check Whisper.cpp installation
   - Verify model paths
   - Check FFmpeg installation

3. **Permission Issues**
   ```bash
   chmod -R 755 files/
   chmod -R 755 logs/
   ```

## License

[Your License] - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Acknowledgments

- [Whisper.cpp](https://github.com/ggerganov/whisper.cpp)
- [MLX](https://github.com/ml-explore/mlx)
- Flask and React communities
