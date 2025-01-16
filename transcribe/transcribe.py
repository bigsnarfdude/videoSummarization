import os
import sys
import timeit
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TranscriptionConfig:
    """Configuration for the transcription service"""
    def __init__(self):
        # Try to get paths from environment variables first
        self.whisper_path = os.getenv('WHISPER_PATH', '/Users/vincent/development/whisper.cpp/main')
        self.model_path = os.getenv('WHISPER_MODEL_PATH', '')
        self.validate()

    def validate(self):
        """Validate the configuration"""
        # Check whisper executable
        if not os.path.exists(self.whisper_path):
            raise FileNotFoundError(
                f"Whisper executable not found at {self.whisper_path}. "
                "Please set WHISPER_PATH environment variable."
            )

        # Check model file
        if not self.model_path:
            # Try to find model in common locations
            common_locations = [
                Path("/Users/vincent/development/whisper.cpp/models"),
                Path.home() / "whisper.cpp/models",
                Path("/usr/local/share/whisper/models"),
                Path("./models")
            ]
            # List of supported model filenames
            model_names = ["ggml-large-v3.bin", "ggml-large-v3.en.bin"]
            
            # Try each model name in each location
            for location in common_locations:
                for model_name in model_names:
                    potential_path = location / model_name
                    if potential_path.exists():
                        self.model_path = str(potential_path)
                        logging.info(f"Found whisper model at: {self.model_path}")
                        break
                if self.model_path:  # If we found a model, stop searching
                    break
            
            if not self.model_path:
                raise FileNotFoundError(
                    f"Could not find whisper model file {model_name} in common locations. "
                    "Please set WHISPER_MODEL_PATH environment variable."
                )

def get_filename(file_path):
    """Returns the filename without extension"""
    return os.path.basename(file_path).split('.')[0]

def validate_audio_file(file_path):
    """Checks if the given path points to a valid WAV audio file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"WAV file not found: {file_path}")
    if not file_path.lower().endswith(".wav"):
        raise ValueError(f"Invalid file format. Expected WAV file, got: {file_path}")

def transcribe(audio_file, output_path="files/transcripts", config=None):
    """
    Transcribes the given audio file using whisper.cpp.
    
    Args:
        audio_file: Path to the WAV audio file
        output_path: Directory to save the transcript
        config: Optional TranscriptionConfig instance
        
    Returns:
        tuple: (elapsed_time, transcript_text, transcript_path)
    """
    try:
        filename_only = get_filename(audio_file)
        validate_audio_file(audio_file)

        # Get or create config
        if config is None:
            config = TranscriptionConfig()

        start_time = timeit.default_timer()
        
        # Verify files exist before running
        logging.info(f"Verifying paths:")
        logging.info(f"  Whisper executable: {config.whisper_path} (exists: {os.path.exists(config.whisper_path)})")
        logging.info(f"  Model file: {config.model_path} (exists: {os.path.exists(config.model_path)})")
        logging.info(f"  Audio file: {audio_file} (exists: {os.path.exists(audio_file)})")

        # Check file permissions
        try:
            os.access(config.whisper_path, os.X_OK) or logging.warning("Whisper executable may not be executable")
            os.access(config.model_path, os.R_OK) or logging.warning("Model file may not be readable")
            os.access(audio_file, os.R_OK) or logging.warning("Audio file may not be readable")
        except Exception as e:
            logging.warning(f"Permission check failed: {e}")

        # Construct command with quoted paths for shell safety
        command = [
            config.whisper_path,
            "-m", config.model_path,
            "-f", audio_file,
            "-l", "en",  # Explicitly set language to English
            "-np",      # No progress
            "-nt"       # No timestamps
        ]

        logging.info(f"Running whisper command: {' '.join(command)}")
        
        # Set working directory to whisper.cpp directory
        whisper_dir = os.path.dirname(config.whisper_path)
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception immediately
            cwd=whisper_dir  # Run from whisper directory
        )

        # Check for errors
        if process.returncode != 0:
            error_msg = process.stderr.strip()
            logging.error(f"Whisper error (code {process.returncode}): {error_msg}")
            if "failed to initialize whisper context" in error_msg:
                raise RuntimeError(
                    f"Failed to initialize whisper model. Please verify model file is valid: {error_msg}"
                )
            raise RuntimeError(f"Transcription failed: {error_msg}")

        # Process output
        processed_str = process.stdout.replace('[BLANK_AUDIO]', '').strip()
        end_time = timeit.default_timer()
        elapsed_time = int(end_time - start_time)

        # Save transcript
        os.makedirs(output_path, exist_ok=True)
        text_path = os.path.join(output_path, f"{filename_only}.txt")
        
        with open(text_path, "w") as file:
            file.write(processed_str)

        logging.info(f"Transcription completed in {elapsed_time}s. Saved to {text_path}")
        return elapsed_time, processed_str, text_path

    except subprocess.CalledProcessError as e:
        error_msg = f"Whisper transcription failed: {e.stderr}"
        logging.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        logging.error(f"Transcription error: {str(e)}")
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
