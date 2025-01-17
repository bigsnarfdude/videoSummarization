import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import spacy
import logging
from mlx_lm import load, generate

from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Global model and tokenizer cache
model: Any = None
tokenizer: Any = None

def get_model_and_tokenizer() -> tuple[Any, Any]:
    """Initialize or return cached model and tokenizer"""
    global model, tokenizer
    if model is None or tokenizer is None:
        try:
            model, tokenizer = load(settings.MLX_MODEL_NAME)
            logger.info("MLX model loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading MLX model: {e}")
            return None, None
    return model, tokenizer

# used for splitting sentences logic
def initialize_spacy() -> Optional[spacy.language.Language]:
    """
    Initialize spaCy with error handling
    
    Returns:
        Optional[spacy.language.Language]: Loaded spaCy model or None if failed
    """
    try:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.info("Downloading spacy model en_core_web_sm...")
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
        return nlp
    except Exception as e:
        logger.error(f"Error initializing spaCy: {e}")
        raise

def create_summary_prompt(chunk: str, title: str) -> str:
    """
    Create a prompt for summarization with enhanced structure
    
    Args:
        chunk: Text chunk to summarize
        title: Title of the content
        
    Returns:
        str: Formatted prompt for the model
    """
    base_prompt = f"""You are a precise and accurate summarizer. Your task is to create a detailed summary of the following text, focusing on extracting specific facts, numbers, and key points. Follow these guidelines:

1. Extract ONLY information that is explicitly stated in the text
2. Use exact numbers, statistics, and quotes when present
3. Maintain the original meaning without adding interpretations

Title: {title}

Text to Summarize:
{chunk}

Create your summary using this structure:
- Start each point with "•" 
- Include specific details and numbers
- Quote important phrases in "quotes" when relevant
- Organize points in logical order
- End with "• Main Takeaway: [core message supported by the text]"

Remember:
- Do not include information not present in the text
- Preserve exact terminology used in the source
- Be specific rather than general
- Focus on facts over opinions

Your precise summary:
"""
    # Apply chat template if available
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template is not None:
        messages = [{"role": "user", "content": base_prompt}]
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    return base_prompt

def count_tokens(text: str) -> int:
    """
    Count tokens in text using the model's tokenizer
    
    Args:
        text: Input text to tokenize
        
    Returns:
        int: Number of tokens
    """
    model, tokenizer = get_model_and_tokenizer()
    if tokenizer is None:
        return 0
    return len(tokenizer.encode(text))

def split_text(text_path: str, title: str) -> List[str]:
    """
    Split text into chunks considering the model's context window
    
    Args:
        text_path: Path to text file
        title: Title of the content
        
    Returns:
        List[str]: List of text chunks
    """
    model, tokenizer = get_model_and_tokenizer()
    if tokenizer is None:
        return []

    # Calculate max tokens for content
    prompt_tokens = count_tokens(create_summary_prompt("", title))
    max_tokens = settings.WINDOW_SIZE - prompt_tokens - 100  # Buffer for generation

    # Initialize spaCy
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

    # Split text into sentences
    doc = nlp(text)
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_tokens = 0

    for sent in doc.sents:
        sent_text = sent.text.strip()
        sent_tokens = count_tokens(sent_text)

        if current_tokens + sent_tokens > max_tokens:
            if current_chunk:  # Save current chunk
                chunks.append(" ".join(current_chunk))
            current_chunk = [sent_text]
            current_tokens = sent_tokens
        else:
            current_chunk.append(sent_text)
            current_tokens += sent_tokens

    if current_chunk:  # Add the last chunk
        chunks.append(" ".join(current_chunk))

    logger.info(f"Split text into {len(chunks)} chunks")
    return chunks

def clean_and_format_summary(raw_summary: str) -> str:
    """
    Clean and format the model's output for consistency
    
    Args:
        raw_summary: Raw model output
        
    Returns:
        str: Cleaned and formatted summary
    """
    import re
    
    # Split into lines and clean up
    lines = raw_summary.strip().split('\n')
    formatted_lines = []
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
            
        line = line.strip()
        
        # Ensure each point starts with a bullet
        if not line.startswith('•'):
            line = re.sub(r'^[-*•]?\s*', '• ', line)
            line = re.sub(r'^\d+\.\s*', '• ', line)
        
        # Ensure consistent spacing after bullet
        line = re.sub(r'^•\s*', '• ', line)
        
        # Fix quotation marks for consistency
        line = re.sub(r'["""]', '"', line)
        
        # Ensure proper spacing around quotes
        line = re.sub(r'(?<!")\s*"', ' "', line)
        line = re.sub(r'"\s*(?!")', '" ', line)
        
        # Clean up multiple spaces
        line = re.sub(r'\s+', ' ', line)
        
        formatted_lines.append(line)
    
    # Ensure main takeaway is at the end
    main_takeaway = None
    other_points = []
    
    for line in formatted_lines:
        if 'main takeaway' in line.lower() or 'main message' in line.lower():
            main_takeaway = line
        else:
            other_points.append(line)
    
    # Combine all points with proper spacing
    result = '\n'.join(other_points)
    if main_takeaway:
        result += '\n\n' + main_takeaway
        
    return result

def summarize_with_mlx(chunk: str, title: str) -> Optional[str]:
    """
    Generate summary for a chunk using MLX model
    
    Args:
        chunk: Text chunk to summarize
        title: Title of the content
        
    Returns:
        Optional[str]: Formatted summary or None if failed
    """
    model, tokenizer = get_model_and_tokenizer()
    if model is None or tokenizer is None:
        logger.error("Model or tokenizer not initialized")
        return None

    try:
        prompt = create_summary_prompt(chunk, title)
        response = generate(
            model, 
            tokenizer, 
            prompt=prompt,
            max_tokens=1024,
            verbose=False
        )
        
        # Clean and format the response
        formatted_summary = clean_and_format_summary(response)
        return formatted_summary
    except Exception as e:
        logger.error(f"Error during summarization: {e}")
        return None

def summarize_in_parallel(chunks: List[str], title: str) -> List[str]:
    """
    Process all chunks to generate summaries
    
    Args:
        chunks: List of text chunks
        title: Title of the content
        
    Returns:
        List[str]: List of summaries
    """
    summaries = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}")
        summary = summarize_with_mlx(chunk, title)
        if summary:
            summaries.append(summary)
    return summaries

def save_summaries(summaries: List[str], filename_only: str) -> str:
    """
    Save generated summaries to file
    
    Args:
        summaries: List of summaries to save
        filename_only: Base filename without extension
        
    Returns:
        str: Path to saved summary file
        
    Raises:
        RuntimeError: If no valid summaries to save
    """
    # Check if we have any valid summaries
    valid_summaries = [s for s in summaries if s]
    if not valid_summaries:
        raise RuntimeError("No valid summaries generated to save")

    summary_path = Path(settings.OUTPUT_DIRS["summaries"]) / f"{filename_only}_summary.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            for i, summary in enumerate(valid_summaries):
                if i > 0:  # Add separator between chunk summaries
                    f.write("\n---\n\n")
                f.write(summary)
                f.write("\n")
        logger.info(f"Summary saved to: {summary_path}")
        return str(summary_path)
    except Exception as e:
        logger.error(f"Error saving summary: {e}")
        raise

if __name__ == "__main__":
    # Test code
    import sys
    if len(sys.argv) > 1:
        text_path = sys.argv[1]
        title = sys.argv[2] if len(sys.argv) > 2 else "Text Summary"
        try:
            chunks = split_text(text_path, title)
            summaries = summarize_in_parallel(chunks, title)
            save_summaries(summaries, Path(text_path).stem)
        except Exception as e:
            logger.error(f"Error in main: {e}")
            sys.exit(1)
