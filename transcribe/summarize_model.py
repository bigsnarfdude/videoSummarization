import os
from pathlib import Path
from typing import List, Optional
import spacy
import logging
import requests
from config import settings

logger = logging.getLogger(__name__)

def initialize_spacy() -> Optional[spacy.language.Language]:
    try:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
        return nlp
    except Exception as e:
        logger.error(f"Error initializing spaCy: {e}")
        raise

def create_summary_prompt(chunk: str, title: str) -> str:
    return f"""You are a precise and accurate summarizer. Create a detailed summary of the following text, focusing on extracting specific facts, numbers, and key points.

Title: {title}

Text to Summarize:
{chunk}

Create your summary using bullet points starting with "•" and end with a main takeaway."""

def split_text(text_path: str, title: str) -> List[str]:
    max_chunk_size = 2000  # Adjust based on model's context window
    
    try:
        nlp = initialize_spacy()
        if nlp is None:
            raise RuntimeError("Failed to initialize spaCy")
    except Exception as e:
        logger.error(f"spaCy initialization error: {e}")
        raise

    try:
        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        logger.error(f"Error reading text file: {e}")
        raise

    doc = nlp(text)
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_size = 0

    for sent in doc.sents:
        sent_text = sent.text.strip()
        sent_size = len(sent_text)

        if current_size + sent_size > max_chunk_size:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [sent_text]
            current_size = sent_size
        else:
            current_chunk.append(sent_text)
            current_size += sent_size

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    logger.info(f"Split text into {len(chunks)} chunks")
    return chunks

def summarize_with_ollama(chunk: str, title: str) -> Optional[str]:
    """Generate summary using Ollama"""
    try:
        prompt = create_summary_prompt(chunk, title)
        response = requests.post(
            f"{settings.OLLAMA_CONFIG['base_url']}/api/generate",
            json={
                "model": settings.OLLAMA_CONFIG["model"],
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": settings.OLLAMA_CONFIG["max_tokens"]
                }
            },
            timeout=settings.OLLAMA_CONFIG["timeout"]
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Error during summarization: {e}")
        return None

def clean_and_format_summary(raw_summary: str) -> str:
    """Clean and format the model's output"""
    import re
    
    lines = raw_summary.strip().split('\n')
    formatted_lines = []
    
    for line in lines:
        if not line.strip():
            continue
            
        line = line.strip()
        if not line.startswith('•'):
            line = re.sub(r'^[-*•]?\s*', '• ', line)
            line = re.sub(r'^\d+\.\s*', '• ', line)
        line = re.sub(r'^•\s*', '• ', line)
        line = re.sub(r'["""]', '"', line)
        line = re.sub(r'(?<!")\s*"', ' "', line)
        line = re.sub(r'"\s*(?!")', '" ', line)
        line = re.sub(r'\s+', ' ', line)
        
        formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)

def summarize_in_parallel(chunks: List[str], title: str) -> List[str]:
    summaries = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}")
        summary = summarize_with_ollama(chunk, title)
        if summary:
            formatted_summary = clean_and_format_summary(summary)
            summaries.append(formatted_summary)
    return summaries

def save_summaries(summaries: List[str], filename_only: str) -> str:
    valid_summaries = [s for s in summaries if s]
    if not valid_summaries:
        raise RuntimeError("No valid summaries generated to save")

    summary_path = Path(settings.OUTPUT_DIRS["summaries"]) / f"{filename_only}_summary.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            for i, summary in enumerate(valid_summaries):
                if i > 0:
                    f.write("\n---\n\n")
                f.write(summary)
                f.write("\n")
        logger.info(f"Summary saved to: {summary_path}")
        return str(summary_path)
    except Exception as e:
        logger.error(f"Error saving summary: {e}")
        raise