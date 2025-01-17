import os
import sys
import timeit
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Optional

from config import settings

# Configure logging using settings
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

class TranscriptionConfig:
    """Configuration for the transcription service"""
    def __init__(self):
        self.whisper_path = settings.WHISPER_PATH
        self.model_path = settings.WHISPER_MODEL_PATH
        self.validate()

    def validate(self):
        """Validate the configuration"""
        if not os.path.exists(self.whisper_path):
            raise FileNotFoundError(f"Whisper executable not found at {self.whisper_path}")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found at {self.model_path}")

def get_filename(file_path: str) -> str:
    """Returns the filename without extension"""
    return os.path.basename(file_path).split('.')[0]

def validate_audio_file(file_path: str) -> None:
    """
    Checks if the given path points to a valid WAV audio file.
    
    Args:
        file_path: Path to the audio file
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a WAV file
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"WAV file not found: {file_path}")
    if not file_path.lower().endswith(".wav"):
        raise ValueError(f"Invalid file format. Expected WAV file, got: {file_path}")

def transcribe(audio_file: str, output_path: str = "files/transcripts", config: Optional[TranscriptionConfig] = None) -> Tuple[int, str, str]:
    """
    Transcribes the given audio file using whisper.cpp.
    
    Args:
        audio_file: Path to the WAV audio file
        output_path: Directory to save the transcript
        config: Optional TranscriptionConfig instance
    
    Returns:
        Tuple containing:
        - Elapsed time in seconds
        - Transcribed text
        - Path to the transcript file
        
    Raises:
        RuntimeError: If transcription fails
    """
    try:
        filename_only = get_filename(audio_file)
        validate_audio_file(audio_file)
        
        logger.info(f"Starting transcription of {audio_file}")
        
        # Get or create config
        if config is None:
            config = TranscriptionConfig()

        # Print debug info
        logger.info("Transcription config:")
        logger.info(f"  Whisper path: {config.whisper_path}")
        logger.info(f"  Model path: {config.model_path}")
        logger.info(f"  Audio file: {audio_file}")

        start_time = timeit.default_timer()
        
        # Set working directory to whisper.cpp directory
        whisper_dir = os.path.dirname(config.whisper_path)
        command = [
            config.whisper_path,
            "-m", config.model_path,
            "-f", os.path.abspath(audio_file),  # Use absolute path for audio file
            "-l", "en",
            "-np",  # No progress bar
            "-nt"   # No timestamps
        ]
        
        logger.info(f"Running command from {whisper_dir}: {' '.join(command)}")
        
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=whisper_dir
        )

        # Log all output regardless of success/failure
        if process.stdout:
            logger.info(f"Whisper stdout: {process.stdout}")
        if process.stderr:
            logger.error(f"Whisper stderr: {process.stderr}")

        # Check for errors
        if process.returncode != 0:
            error_msg = process.stderr.strip()
            logger.error(f"Whisper error (code {process.returncode}): {error_msg}")
            if "failed to initialize whisper context" in error_msg:
                raise RuntimeError(
                    f"Failed to initialize whisper model. Please verify model file is valid: {error_msg}"
                )
            raise RuntimeError(f"Transcription failed: {error_msg}")

        # Process output
        processed_str = process.stdout.replace('[BLANK_AUDIO]', '').strip()
        if not processed_str:
            logger.error("No transcript generated (empty output)")
            raise RuntimeError("Transcription produced empty output")
            
        end_time = timeit.default_timer()
        elapsed_time = int(end_time - start_time)

        # Ensure output_path is absolute and exists
        output_path = os.path.abspath(output_path)
        os.makedirs(output_path, exist_ok=True)
        text_path = os.path.join(output_path, f"{filename_only}.txt")
        
        logger.info(f"Writing transcript of length {len(processed_str)} to {text_path}")
        
        with open(text_path, "w") as file:
            file.write(processed_str)

        logger.info(f"Transcription completed in {elapsed_time}s. Saved to {text_path}")
        return elapsed_time, processed_str, text_path

    except subprocess.CalledProcessError as e:
        error_msg = f"Whisper transcription failed: {e.stderr}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise

if __name__ == "__main__":
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
        try:
            elapsed_time, transcript, transcript_path = transcribe(audio_path)
            print(f"Audio transcribed in {elapsed_time} seconds")
            print(f"Transcript saved to: {transcript_path}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Usage: python transcribe.py <audio_path>")
