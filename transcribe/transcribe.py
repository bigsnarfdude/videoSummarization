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
    """
    Transcribes audio using faster-whisper.
    Returns (elapsed_time, transcribed_text, transcript_path)
    """
    try:
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        filename_only = Path(audio_file).stem
        logger.info(f"Starting transcription of {audio_file}")

        start_time = timeit.default_timer()
        
        # Initialize model
        model = WhisperModel(
            model_size="large-v3",
            device="cuda", 
            compute_type="float16"
        )

        # Transcribe
        segments, info = model.transcribe(
            audio_file,
            beam_size=5
        )

        logger.info(f"Detected language '{info.language}' with probability {info.language_probability}")

        # Combine segments
        transcript_parts = []
        for segment in segments:
            transcript_parts.append(segment.text)
        
        processed_str = " ".join(transcript_parts).strip()
        
        if not processed_str:
            logger.error("No transcript generated (empty output)")
            raise RuntimeError("Transcription produced empty output")

        end_time = timeit.default_timer()
        elapsed_time = int(end_time - start_time)

        # Save transcript
        os.makedirs(output_path, exist_ok=True)
        text_path = os.path.join(output_path, f"{filename_only}.txt")
        
        with open(text_path, "w") as f:
            f.write(processed_str)

        logger.info(f"Transcription completed in {elapsed_time}s. Saved to {text_path}")
        return elapsed_time, processed_str, text_path

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