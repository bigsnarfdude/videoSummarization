#!/usr/bin/env python3
"""
Complete video processing pipeline for BIRS videos
Download → Audio extraction → Transcription → Normalization → Summarization
"""
import sys
import os
import requests
from pathlib import Path
from transcribe.get_video import extract_audio_dual
from normalize_transcript import normalize_transcript
from faster_whisper import WhisperModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_video(url: str, output_path: str) -> str:
    """Download video from videos.birs.ca"""
    logger.info(f"Downloading: {url}")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    logger.info(f"Downloaded: {output_path}")
    return output_path


def transcribe_audio(wav_path: str) -> str:
    """Transcribe audio using Whisper large-v3"""
    import torch
    import gc

    logger.info(f"Loading Whisper large-v3...")
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")

    logger.info(f"Transcribing: {wav_path}")
    # Reduce batch size and beam size to save VRAM
    segments, info = model.transcribe(
        wav_path,
        beam_size=3,  # Reduced from 5
        vad_filter=True,  # Voice activity detection to skip silence
        vad_parameters=dict(min_silence_duration_ms=500)
    )

    transcript = " ".join([segment.text for segment in segments])

    logger.info(f"Transcription complete: {len(transcript)} chars, {len(transcript.split())} words")
    logger.info(f"Language: {info.language}, Duration: {info.duration:.1f}s")

    # Clean up GPU memory
    del model
    gc.collect()
    torch.cuda.empty_cache()
    logger.info("GPU memory cleared")

    return transcript


def summarize_transcript(transcript: str, title: str) -> str:
    """Summarize transcript using gpt-oss:20b via Ollama"""
    logger.info("Generating summary with gpt-oss:20b...")

    # Split into chunks if needed (2000 words per chunk)
    words = transcript.split()
    chunk_size = 2000
    chunks = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

    summaries = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")

        prompt = f"""You are a precise and accurate summarizer. Create a detailed summary of the following text, focusing on extracting specific facts, numbers, and key points.

Title: {title}

Text to Summarize:
{chunk}

Create your summary using bullet points starting with "•" and end with a main takeaway."""

        response = requests.post('http://localhost:11434/api/generate', json={
            'model': 'gpt-oss:20b',
            'prompt': prompt,
            'stream': False,
            'keep_alive': 0  # Unload model immediately after use
        }, timeout=600)  # 10 minutes per chunk (was 180s/3min)

        summary = response.json()['response']
        summaries.append(summary)

    # Combine summaries
    combined = "\n\n---\n\n".join(summaries)
    logger.info(f"Summary complete: {len(combined)} chars")

    return combined


def process_video(video_url: str, basename: str):
    """
    Complete pipeline for processing one video

    Args:
        video_url: URL to video file (e.g., https://videos.birs.ca/2025/25w5318/202507210900-Walton.mp4)
        basename: Base name for output files (e.g., 25w5318_202507210900_Walton)
    """
    # Create output directories
    dirs = {
        'downloads': Path('files/downloads'),
        'audio_wav': Path('files/audio/wav'),
        'audio_mp3': Path('files/audio/mp3'),
        'transcripts': Path('files/transcripts'),
        'summaries': Path('files/summaries')
    }

    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Download video
        video_path = dirs['downloads'] / f"{basename}.mp4"
        if not video_path.exists():
            download_video(video_url, str(video_path))
        else:
            logger.info(f"Video already downloaded: {video_path}")

        # Step 2: Extract audio (WAV + MP3)
        logger.info("Extracting audio...")
        audio_files = extract_audio_dual(str(video_path), basename)
        wav_path = audio_files['wav']
        mp3_path = audio_files['mp3']
        logger.info(f"Audio extracted: WAV={wav_path}, MP3={mp3_path}")

        # Step 3: Transcribe
        transcript_raw = transcribe_audio(wav_path)

        # Step 4: Normalize transcript
        logger.info("Normalizing transcript...")
        transcript_clean = normalize_transcript(transcript_raw)
        logger.info(f"Normalized: {len(transcript_raw)} → {len(transcript_clean)} chars")

        # Save transcript
        transcript_path = dirs['transcripts'] / f"{basename}.txt"
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript_clean)
        logger.info(f"Transcript saved: {transcript_path}")

        # Step 5: Summarize
        summary = summarize_transcript(transcript_clean, basename)

        # Save summary
        summary_path = dirs['summaries'] / f"{basename}_summary.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        logger.info(f"Summary saved: {summary_path}")

        # Step 6: Cleanup (delete video and WAV, keep MP3)
        logger.info("Cleaning up temporary files...")
        os.remove(video_path)
        os.remove(wav_path)
        logger.info(f"Deleted: {video_path}, {wav_path}")
        logger.info(f"Kept: {mp3_path}, {transcript_path}, {summary_path}")

        logger.info(f"✅ Processing complete for {basename}")
        return {
            'mp3': mp3_path,
            'transcript': transcript_path,
            'summary': summary_path,
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"❌ Error processing {basename}: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python process_video.py <video_url> <basename>")
        print("Example: python process_video.py https://videos.birs.ca/2025/25w5318/202507210900-Walton.mp4 25w5318_202507210900_Walton")
        sys.exit(1)

    video_url = sys.argv[1]
    basename = sys.argv[2]

    result = process_video(video_url, basename)

    if result['status'] == 'success':
        print(f"\n✅ SUCCESS!")
        print(f"MP3: {result['mp3']}")
        print(f"Transcript: {result['transcript']}")
        print(f"Summary: {result['summary']}")
    else:
        print(f"\n❌ FAILED: {result['error']}")
        sys.exit(1)
