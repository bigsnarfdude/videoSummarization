# VideoLLM

UPDATED

VideoLLM is an AI-powered application for processing and analyzing video and audio lectures. 
It transcribes videos/audio, generates summaries, 
and creates structured notes for improved learning efficiency.

https://gist.github.com/bigsnarfdude/7f2e2098e41044886dfe2d9d3344fc5c

## Features

- Video and Audio transcription using Faster-Whisper
- AI-powered summarization with Ollama GPT-OSS
- Automated Logseq note generation
- Interactive LLM chat interface for content exploration using Ollama Gemma 3 QAT (working on visual QA)
- Analytics dashboard for content insights

## Prerequisites

- Python 3.9+
- FFmpeg
- Ollama

## Installation

1. Clone and setup environment:
```bash
git clone <repository-url>
cd videoLLM
python -m venv venv
source venv/bin/activate  # Unix/macOS

```

2. Install FFmpeg:
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt-get install ffmpeg

# Windows: Download from ffmpeg.org
```

3. Install Ollama and model:
```bash
# Install Ollama from ollama.ai
ollama pull google/gemma-3-27b-it-qat-q4_0-gguf
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Create required directories:
```bash
mkdir -p files/{uploads,audio,transcripts,summaries,logseq,stats} logs
```

## Usage

Start the server:
```bash
python app.py
```

Access interfaces:
- Main interface: http://localhost:5000
- Admin dashboard: http://localhost:5000/admin
- Chat interface: http://localhost:5000/chat
- Reports interface: http://localhost:5000/reports

## API Endpoints

### Process Video
- `POST /api/v1/process`
  - Upload and process video file
  - Returns paths to generated files (audio, transcript, summary, etc.)

### Admin Analytics
- `GET /admin/api/stats`
  - Get overall processing statistics
- `GET /admin/api/lecture/<lecture_name>`
  - Get stats for specific lecture

### Chat Interface
- `POST /ollama/chat`
  - Send queries to chat with processed content
- `GET /ollama/status`
  - Check Ollama service status

### File Management
- `GET /list-transcripts`
  - List all available transcripts
- `GET /transcripts/<filename>`
  - Get specific transcript content

## Documentation

See source code docstrings for detailed API documentation.

## Contributing

1. Fork repository
2. Create feature branch
3. Commit changes
4. Submit pull request

## License

MIT
