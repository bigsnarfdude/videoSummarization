import os
import spacy
import logging
from mlx_lm import load, generate

# Constants
SUMMARY_DIR = "files/summaries"
MODEL_NAME = "mlx-community/phi-4-8bit"
WINDOW_SIZE = 4096  # Adjust based on phi-4 context window

# Configure logging
logging.basicConfig(
    filename="summarization.log", 
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Global model and tokenizer cache
model, tokenizer = None, None

def get_model_and_tokenizer():
    """Initialize or return cached model and tokenizer"""
    global model, tokenizer
    if model is None or tokenizer is None:
        try:
            model, tokenizer = load(MODEL_NAME)
            logging.info("MLX model loaded successfully.")
        except Exception as e:
            logging.error(f"Error loading MLX model: {e}")
            return None, None
    return model, tokenizer

def initialize_spacy():
    """Initialize spaCy with error handling"""
    try:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            logging.info("Downloading spacy model en_core_web_sm...")
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
        return nlp
    except Exception as e:
        logging.error(f"Error initializing spaCy: {e}")
        raise

def create_summary_prompt(chunk, title):
    """Create a prompt for summarization with enhanced structure for better outputs"""
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

def count_tokens(text):
    """Count tokens in text using the model's tokenizer"""
    model, tokenizer = get_model_and_tokenizer()
    if tokenizer is None:
        return 0
    return len(tokenizer.encode(text))

def split_text(text_path, title):
    """Split text into chunks considering the model's context window"""
    model, tokenizer = get_model_and_tokenizer()
    if tokenizer is None:
        return []

    # Calculate max tokens for content based on model window size
    prompt_tokens = count_tokens(create_summary_prompt("", title))
    max_tokens = WINDOW_SIZE - prompt_tokens - 100  # Buffer for generation

    # Initialize spaCy
    try:
        nlp = initialize_spacy()
        if nlp is None:
            raise RuntimeError("Failed to initialize spaCy")
    except Exception as e:
        logging.error(f"spaCy initialization error: {e}")
        raise

    try:
        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        logging.error(f"Error reading text file: {e}")
        raise

    # Split text into sentences
    doc = nlp(text)
    chunks = []
    current_chunk = []
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

    logging.info(f"Split text into {len(chunks)} chunks")
    return chunks

def clean_and_format_summary(raw_summary):
    """Clean and format the model's output for consistency"""
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
            # Handle cases where model used different bullet points or numbers
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

def summarize_with_mlx(chunk, title):
    """Generate summary for a chunk using MLX model with enhanced output processing"""
    model, tokenizer = get_model_and_tokenizer()
    if model is None or tokenizer is None:
        logging.error("Model or tokenizer not initialized")
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
        logging.error(f"Error during summarization: {e}")
        return None

def summarize_in_parallel(chunks, title):
    """Process all chunks to generate summaries"""
    summaries = []
    for i, chunk in enumerate(chunks):
        logging.info(f"Processing chunk {i+1}/{len(chunks)}")
        summary = summarize_with_mlx(chunk, title)
        if summary:
            summaries.append(summary)
    return summaries

def save_summaries(summaries, filename_only):
    """Save generated summaries to file"""
    # Check if we have any valid summaries
    valid_summaries = [s for s in summaries if s]
    if not valid_summaries:
        raise RuntimeError("No valid summaries generated to save")

    os.makedirs(SUMMARY_DIR, exist_ok=True)
    summary_path = os.path.join(SUMMARY_DIR, f"{filename_only}_summary.txt")
    
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            for i, summary in enumerate(valid_summaries):
                if i > 0:  # Add separator between chunk summaries
                    f.write("\n---\n\n")
                f.write(summary)
                f.write("\n")
        logging.info(f"Summary saved to: {summary_path}")
        return summary_path
    except Exception as e:
        logging.error(f"Error saving summary: {e}")
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
            save_summaries(summaries, os.path.splitext(os.path.basename(text_path))[0])
        except Exception as e:
            logging.error(f"Error in main: {e}")
            sys.exit(1)
