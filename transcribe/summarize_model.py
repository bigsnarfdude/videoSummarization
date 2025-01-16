import os
import spacy
import logging
from mlx_lm import load, generate

# Constants
SUMMARY_DIR = "files/summaries"
MODEL_NAME = "mlx-community/phi-4-8bit"
WINDOW_SIZE = 4096  # Adjust based on phi-4 context window

# Configure logging
logging.basicConfig(filename="summarization.log", level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load model and tokenizer (cached version)
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

def create_summary_prompt(chunk, title):
    """Create a prompt for summarization"""
    base_prompt = f"""Create a clear and concise bullet-point summary of the following text. Focus on the key facts, claims, and arguments presented.

Title: {title}

Text:
{chunk}

Please provide your summary in bullet points, and end with a "Main Message" bullet point that captures the core idea:"""

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

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logging.info("Downloading spacy model en_core_web_sm...")
        import spacy.cli
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")

    try:
        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        logging.error(f"Error reading text file: {e}")
        return []

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

def summarize_with_mlx(chunk, title):
    """Generate summary for a chunk using MLX model"""
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
            max_tokens=1024,  # Adjust based on desired summary length
            verbose=False
        )
        return response.strip()
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
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    summary_path = os.path.join(SUMMARY_DIR, f"{filename_only}_summary.txt")
    
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            for i, summary in enumerate(summaries):
                if i > 0:  # Add separator between chunk summaries
                    f.write("\n---\n\n")
                f.write(summary)
                f.write("\n")
        logging.info(f"Summary saved to: {summary_path}")
        return summary_path
    except Exception as e:
        logging.error(f"Error saving summary: {e}")
        return None

if __name__ == "__main__":
    # Test code
    import sys
    if len(sys.argv) > 1:
        text_path = sys.argv[1]
        title = sys.argv[2] if len(sys.argv) > 2 else "Text Summary"
        chunks = split_text(text_path, title)
        summaries = summarize_in_parallel(chunks, title)
        save_summaries(summaries, os.path.splitext(os.path.basename(text_path))[0])
