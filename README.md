# LLM Based Video Transcription and Summarization API

This project provides both a command-line tool and a REST API for transcribing and summarizing video files. It uses Whisper.cpp for transcription and MLX Phi4 for summarization, generating text summaries and Logseq-compatible Markdown notes.

## Features

- Video to audio conversion using FFmpeg
- Speech-to-text transcription using Whisper.cpp
- Text summarization using MLX large language model
- Logseq-compatible note generation
- REST API for remote processing
- Comprehensive logging and error handling

## Project Structure

```
.
├── app.py              (Flask API server)
├── transcribe.py       (Main CLI script)
├── transcribe/         (Core package)
│   ├── __init__.py
│   ├── summarize_model.py (LLM summarization)
│   ├── transcribe.py     (Whisper transcription)
│   ├── get_video.py      (Video processing)
│   └── utils.py          (Utilities)
├── files/
│   ├── uploads/          (Temporary video uploads)
│   ├── audio/           (Extracted audio)
│   ├── transcripts/     (Text transcripts)
│   ├── summaries/       (Generated summaries)
│   └── logseq/          (Logseq notes)
├── *.log               (Log files)
└── requirements.txt    (Dependencies)
```

## Prerequisites

- **Python 3.7+** ([python.org](https://python.org/))
- **Whisper.cpp** ([GitHub Repository](https://github.com/ggerganov/whisper.cpp))
  - Build and ensure the `main` executable is in your PATH
- **FFmpeg** ([ffmpeg.org](https://ffmpeg.org/))
  - macOS: `brew install ffmpeg`
  - Ubuntu: `apt-get install ffmpeg`
- **MLX** (Follow MLX installation instructions)
- **Spacy Model**:
  ```bash
  python -m spacy download en_core_web_sm
  ```

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-name>
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Unix/macOS
   .venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The application uses several configuration constants that can be modified in `app.py`:

```python
UPLOAD_FOLDER = 'files/uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
LOG_FILE = "api.log"
SUMMARIES_DIR = "files/summaries"
LOGSEQ_DIR = "files/logseq"
```

## Usage

### REST API

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. The API will be available at `http://localhost:5000`

#### Endpoints

1. **Process Video** (`POST /api/process`)
   - Multipart form data:
     - `file`: Video file (required)
     - `title`: Video title (optional)
   
   Example using curl:
   ```bash
   curl -X POST \
     -F "file=@/path/to/video.mp4" \
     -F "title=My Video Title" \
     http://localhost:5000/api/process
   ```

   Response:
   ```json
   {
       "status": "success",
       "files": {
           "audio": "video_name.wav",
           "transcript": "video_name.txt",
           "summary": "video_name.txt",
           "logseq": "video_name.md"
       }
   }
   ```

2. **Check Status** (`GET /api/status`)
   ```bash
   curl http://localhost:5000/api/status
   ```

### Command Line Interface

The original CLI is still available:

```bash
python transcribe.py --input_path "/path/to/video.mp4" --title "Video Title"
```

## Output Files

The process generates several files:

1. **Audio** (`files/audio/*.wav`): Extracted audio in WAV format
2. **Transcript** (`files/transcripts/*.txt`): Raw text transcription
3. **Summary** (`files/summaries/*.txt`): Bullet-point summary
4. **Logseq Note** (`files/logseq/*.md`): Formatted Markdown note

## Logging

The application maintains several log files:
- `api.log`: API-specific logs
- `transcribe.log`: Transcription process logs
- `summarization.log`: Summarization process logs
- `video_processing.log`: Video/audio conversion logs

## Error Handling

The API includes comprehensive error handling for:
- Invalid file types
- Missing files
- Processing errors
- File system errors

All errors are logged and returned with appropriate HTTP status codes.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Troubleshooting

### Common Issues

1. **ModuleNotFoundError**
   - Verify virtual environment is activated
   - Reinstall requirements: `pip install -r requirements.txt`

2. **FileNotFoundError**
   - Check paths to Whisper model and FFmpeg
   - Verify directory permissions

3. **Processing Errors**
   - Check log files for detailed error messages
   - Verify input video format is supported
   - Ensure sufficient disk space

### Performance Tips

1. For large videos:
   - Process in smaller chunks
   - Monitor system resources
   - Adjust chunk sizes in `summarize_model.py`

2. For faster processing:
   - Use GPU acceleration if available
   - Optimize audio quality settings
   - Adjust model parameters

## License

MIT

## Acknowledgments

- Whisper.cpp project
- MLX project
- FFmpeg project

  ## TODO
  https://gist.github.com/bigsnarfdude/f1a8b31f3cbb4449cc6c79ff68603583 find and visual papers in same genre
  refactor

```
import mlx_whisper

target = "path/to/audioFile"
transcription_model = "mlx-community/whisper-large-v3-mlx"
transcribed = mlx_whisper.transcribe(target,path_or_hf_repo=transcription_model)

print(transcribed["text"])

```
