# VideoLLLM -  An AI-first app, grounded in your own video lecture, designed to help you gain insights faster.

VideoLLM is an AI-powered tool that helps users analyze video lectures (make new documents, take notes, and generate content). It's designed to help learners synthesize information from multiple sources and make connections faster.

## Key Features

- 🎥 Video Processing
  - Supports MP4, AVI, MOV, and MKV formats
  - Automatic audio extraction
  - High-accuracy transcription using Whisper.cpp

- 📊 Content Analysis
  - Text summarization using MLX Phi-4 model
  - Topic and concept extraction
  - Mathematical content analysis
  - Complexity scoring
  - Auto-generated Logseq notes

- 📈 Admin Dashboard
  - Real-time processing statistics
  - Word count analytics
  - Topic and concept visualization
  - Content trend analysis

- 🎥 Chat with VideoLLM
  - Real-time chat with the created documents
  - Learn more about your document
  - Use natural language 
  - Interogate the lecture

## Prerequisites

- Python 3.9+
- FFmpeg
- Whisper.cpp
- MLX
- Ollama

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/videoSummarization.git
cd videoSummarization
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Unix/macOS
# OR
venv\Scripts\activate     # Windows
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install external dependencies:

FFmpeg:
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt-get install ffmpeg

# Windows
# Download from ffmpeg.org
```

Whisper.cpp:
```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
make
# Download model: large-v3
bash ./models/download-ggml-model.sh large-v3
```

5. Configure environment:
```bash
cp .env.example .env
```

Edit .env to set:
```env
SECRET_KEY=your-secret-key
WHISPER_PATH=/path/to/whisper/executable
WHISPER_MODEL_PATH=/path/to/whisper/model
MLX_MODEL_NAME=mlx-community/phi-4-8bit
```

6. Create required directories:
```bash
mkdir -p files/{uploads,audio,transcripts,summaries,logseq,stats} logs
```

## Project Structure

```
videoSummarization/
├── admin/                 # Admin dashboard
│   ├── api_routes.py      # API endpoints
│   ├── lecture_stats.py   # Statistics tracking
│   └── math_analytics.py  # Content analysis
│   └── routes.py          # Routes
├── transcribe/            # Core processing
│   ├── get_video.py       # Video handling
│   ├── processor.py       # Main processing
│   ├── summarize_model.py # MLX integration
│   ├── transcribe.py      # Whisper integration
│   └── utils.py           # Utilities
├── templates/             # Frontend templates
│   └── admin
│       └── dashboard.html # Analytics template
│   ├── base.html          # Base template
│   ├── chat.html          # LLM Chat template
│   └── index.html         # Upload template
├── static/                # Static assets
├── app.py                 # Flask application
├── config.py              # Configuration
└── main.py                # CLI Video Processing
└── requirements.txt   # Dependencies
```

## Usage

### Starting the Server

Development mode:
```bash
python app.py
```

Production mode:
```bash
export APP_ENV=production
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Web Interface

1. Access `http://localhost:5000`
2. Upload video through drag-and-drop or file selection
3. Wait for processing completion
4. Access generated files and insights

### Admin Dashboard

1. Access `http://localhost:5000/admin`
2. View statistics and analytics:
   - Word count distribution
   - Topic categorization
   - Content trends
   - Processing metrics

### API Endpoints

Process video:
```bash
curl -X POST \
  -F "file=@/path/to/video.mp4" \
  -F "title=Video Title" \
  http://localhost:5000/api/v1/process
```

Check status:
```bash
curl http://localhost:5000/api/v1/status
```

## Output Files

The platform generates several files for each processed video:

- `files/audio/*.wav`: Extracted audio (16kHz, mono)
- `files/transcripts/*.txt`: Raw transcriptions
- `files/summaries/*.txt`: Generated summaries
- `files/logseq/*.md`: Logseq-compatible notes
- `files/stats/*.json`: Processing statistics and analysis

## Development

### Running Tests
```bash
pytest
```

### Code Style
```bash
flake8 .
black .
```

### Adding New Features

1. Create feature branch
2. Add tests
3. Implement feature
4. Update documentation
5. Submit pull request

## Troubleshooting

### Common Issues

1. **File Upload Errors**
   - Check file size limits in config.py
   - Verify allowed file types
   - Ensure upload directory permissions

2. **Processing Errors**
   - Verify Whisper.cpp installation
   - Check model paths
   - Monitor logs/app.log

3. **Permission Issues**
   ```bash
   chmod -R 755 files/
   chmod -R 755 logs/
   ```

4. **MLX Model Issues**
   - Verify model availability
   - Check internet connection
   - Monitor system resources

5. **Ollama Model Issues**
   - Verify model availability
   - Check internet connection
   - Monitor system resources

## Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Run tests
5. Submit pull request

## License

MIT

## Acknowledgments

- [Whisper.cpp](https://github.com/ggerganov/whisper.cpp) for transcription
- [MLX](https://github.com/ml-explore/mlx) for analysis
- [Flask](https://flask.palletsprojects.com/) framework
- [Tailwind CSS](https://tailwindcss.com/) for styling
- [Ollama](https://ollama.com/download) for chat
- [FFMpeg](https://www.ffmpeg.org/) for video -> audio processing

