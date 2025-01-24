import os
import sys
import timeit
import logging
from pathlib import Path
from typing import Tuple, Optional
from faster_whisper import WhisperModel

from config import settings

logger = logging.getLogger(__name__)

def transcribe(audio_file: str, output_path: str = "files/transcripts") -> Tuple[int, str, str]:
    try:
        if not Path(audio_file).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        filename_only = Path(audio_file).stem
        logger.info(f"Starting transcription of {audio_file}")
        
        start_time = timeit.default_timer()
        
        # Initialize Whisper model with required parameters
        model = WhisperModel(
            model_size_or_path=settings.TRANSCRIPTION_CONFIG["model_size"],
            device=settings.TRANSCRIPTION_CONFIG["device"],
            compute_type=settings.TRANSCRIPTION_CONFIG["compute_type"]
        )
        
        # Perform transcription
        segments, info = model.transcribe(
            audio_file,
            beam_size=settings.TRANSCRIPTION_CONFIG["beam_size"]
        )
        
        logger.info(f"Detected language '{info.language}' with probability {info.language_probability}")
        
        processed_str = " ".join(segment.text for segment in segments).strip()
        
        if not processed_str:
            logger.error("No transcript generated (empty output)")
            raise RuntimeError("Transcription produced empty output")

        end_time = timeit.default_timer()
        elapsed_time = int(end_time - start_time)

        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        text_path = output_path / f"{filename_only}.txt"
        
        text_path.write_text(processed_str)
        logger.info(f"Transcription completed in {elapsed_time}s. Saved to {text_path}")
        return elapsed_time, processed_str, str(text_path)

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