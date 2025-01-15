# Transcribe and Summarize Videos

This project provides a command-line tool to transcribe and summarize video files using Whisper.cpp for transcription and a large language model (LLM) through MLX for summarization. The output includes text summaries and Logseq-compatible Markdown notes.

## Project Structure

```
.
├── transcribe.py        (Main script)
├── transcribe/         (Package containing modules)
│   ├── __init__.py
│   ├── summarize_model.py (LLM summarization logic)
│   ├── transcribe.py     (Transcription logic)
│   ├── get_video.py      (Video/audio processing)
│   └── utils.py          (Utility functions)
├── files/
│   ├── audio/            (Extracted audio files)
│   ├── summaries/        (Generated text summaries)
│   └── logseq/           (Logseq Markdown notes)
├── transcribe.log      (Log file)
└── requirements.txt    (Project dependencies)
```

## Prerequisites

Before using this tool, ensure you have the following:

*   **Python 3.7+:** Download and install the latest version from [python.org](https://www.python.org/).
*   **Whisper.cpp:** Follow the installation instructions on the [Whisper.cpp repository](https://github.com/ggerganov/whisper.cpp). Ensure the `main` executable is in your PATH or you know its exact path.
*   **FFmpeg:** Install FFmpeg for video/audio processing. On macOS, you can use `brew install ffmpeg`. On other systems, follow the instructions on the [FFmpeg website](https://ffmpeg.org/).
*   **MLX:** Install MLX following the instructions on the relevant documentation.
*   **Spacy Model:** Download the English language model:
    ```bash
    python -m spacy download en_core_web_sm
    ```

## Installation

1.  **Clone the repository:**

    ```bash
    git clone [https://your-repository-url.git](https://your-repository-url.git) # Replace with your repo URL
    cd your-repository-name
    ```

2.  **Create a virtual environment (recommended):**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On macOS/Linux
    .venv\Scripts\activate     # On Windows
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

## Configuration

*   **Model Paths:** The paths to the Whisper.cpp model and the output directories are configured within the Python scripts (`transcribe.py`, `get_video.py`, `summarize_model.py`). You might need to adjust these paths to match your system setup.

## Usage

To transcribe and summarize a video, use the following command:

```bash
python transcribe.py --input_path "/path/to/your/video.mp4" --title "My Video Title"
```

*   `--input_path`: The path to the video file you want to process.
*   `--title`: The title of the video, which will be used in the Logseq note.

**Example:**

```bash
python transcribe.py --input_path "videos/my_lecture.mp4" --title "Introduction to Quantum Physics"
```

## Output

The script will generate the following output:

*   **Extracted Audio:** The audio from the video will be extracted and saved in the `files/audio/` directory.
*   **Text Transcript:** The transcribed text will be saved as a `.txt` file in the `files/transcripts/` directory (created by `transcribe.py`).
*   **Text Summary:** The summarized text will be saved as a `.txt` file in the `files/summaries/` directory.
*   **Logseq Note:** A Markdown file formatted for Logseq will be created in the `files/logseq/` directory. This file will contain the summary and a link back to the video title.
*   **Log File:** A log file named `transcribe.log` will be created in the project root to record the script's activity and any errors.

## Troubleshooting

*   **`ModuleNotFoundError`:** Ensure all dependencies are installed in your virtual environment.
*   **`FileNotFoundError`:** Double-check file paths for the video, Whisper model, and output directories.
*   **Errors in the Log File:** Consult the `transcribe.log` file for detailed error messages.

## TODO

*   Implement a Flask web interface for easier use.
*   Add support for other summarization models.
*   Improve error handling and input validation. the project structure.
*   **Emphasis on Commands:** Used backticks (\`) to format commands for better readability.
*   **Repository URL Placeholder:** Added a placeholder for the repository URL.
