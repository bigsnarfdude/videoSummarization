from pathlib import Path
from typing import Dict, List, TypedDict
from pydantic_settings import BaseSettings, SettingsConfigDict
import os 

class TranscriptionConfig(TypedDict):
    model_size: str
    device: str
    compute_type: str
    beam_size: int
    language: str

class OllamaConfig(TypedDict):
    base_url: str
    model: str
    timeout: int
    max_tokens: int

class Settings(BaseSettings):
    """Application settings with validation using Pydantic"""
    
    APP_NAME: str = "Video Processing Service"
    APP_ENV: str = "development" 
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-here"
    
    # Security: localhost-only access (SSH tunnel required)
    HOST: str = "127.0.0.1"  # localhost only, no external access
    PORT: int = 5000
    WORKERS: int = 2  # Reduced for nigel
    
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS: List[str] = ["mp4", "avi", "mov", "mkv", "mp3"]
    MAX_FILENAME_LENGTH: int = 100
    
    WINDOW_SIZE: int = 4096
    
    BASE_DIR: Path = Path(__file__).resolve().parent
    
    OUTPUT_DIRS: Dict[str, Path] = {
        "uploads": BASE_DIR / "files/uploads",
        "downloads": BASE_DIR / "files/downloads",  # Temporary video downloads
        "audio_wav": BASE_DIR / "files/audio/wav",  # Temporary WAV for transcription
        "audio_mp3": BASE_DIR / "files/audio/mp3",  # Keep MP3 for audio.birs.ca
        "transcripts": BASE_DIR / "files/transcripts",
        "summaries": BASE_DIR / "files/summaries",
        "logseq": BASE_DIR / "files/logseq",
        "stats": BASE_DIR / "files/stats"
    }
    
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Path = BASE_DIR / "logs/app.log"
    
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_WINDOW: int = 60
    
    # Archive scraping config
    ARCHIVE_BASE_URL: str = "https://videos.birs.ca"
    ARCHIVE_YEARS: List[int] = [2025, 2026]  # Only scrape new years
    SCRAPE_INTERVAL: int = 3600  # Hourly (in seconds)
    BATCH_SIZE: int = 10  # Process 10 videos per hour

    # Database
    DB_PATH: Path = BASE_DIR / "data/archive.db"

    TRANSCRIPTION_CONFIG: TranscriptionConfig = {
        "model_size": "large-v3",  # Will use Parakeet instead
        "device": "cuda",
        "compute_type": "float16",
        "beam_size": 5,
        "language": "en"
    }

    # Parakeet TDT config (replaces Whisper)
    USE_PARAKEET: bool = True
    PARAKEET_MODEL: str = "nvidia/parakeet-tdt-0.6b-v2"
    PARAKEET_CHUNK_DURATION: int = 1440  # 24 minutes in seconds

    OLLAMA_CONFIG: OllamaConfig = {
        "base_url": "http://localhost:11434",
        "model": "gpt-oss:20b",
        "timeout": 180,
        "max_tokens": 2048
    }
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
