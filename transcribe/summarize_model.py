import os
import spacy
import logging
from mlx_lm import load, generate

# Constants
PROMPT = """
Create a bullet point summary of the text that will follow after the heading `TEXT:`. 

Do not just list the general topic, but the actual facts that were shared.

For example, if a speaker claims that "a dosage of X increases Y", do not
just write "the speaker disusses the effects of X", instead write "a dosage 
of X increases Y".

Use '- ' for bullet points:

After you have made all bullet points, add one last bullet point that 
summarizes the main message of the content, like so:

- Main message: [MAIN MESSAGE HERE]

---

TEXT TITLE: {title}

TEXT:
{chunk}
"""
MODEL_MAX_TOKENS = 8192
WINDOW_SIZE = 4096
SUMMARY_DIR = "files/summaries"

# Configure logging
logging.basicConfig(filename="summarization.log", level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load model and tokenizer (cached version)
model, tokenizer = None, None
def get_model_and_tokenizer():
    global model, tokenizer
    if model is None or tokenizer is None:
        try:
            model, tokenizer = load("mistralai/Mistral-7B-Instruct-v0.2")
            logging.info("MLX model loaded successfully.")
        except Exception as e:
            logging.error(f"Error loading MLX model: {e}")
            return None, None
    return model, tokenizer

def count_tokens(text, tokenizer):
    """Counts tokens in a text string using the MLX model's tokenizer."""
    if tokenizer is None:
        logging.error("Tokenizer not initialized.")
        return 0
    return len(tokenizer.encode(text))

def split_text(text_path, title):
    """Splits text into chunks considering the MLX model's window size."""
    model, tokenizer = get_model_and_tokenizer()
    if tokenizer is None:
        return []

    prompt_tokens = count_tokens(PROMPT.format(chunk="", title=title), tokenizer)
    max_tokens = WINDOW_SIZE - prompt_tokens

    try:
        nlp = spacy.load("en_core_web_sm")
        nlp.add_pipe("sentencizer")
    except OSError:
        logging.error("Downloading spacy model en_core_web_sm. Please wait...")
        import spacy.cli
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
        nlp.add_pipe("sentencizer")

    try:
        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        logging.error(f"Text file not found: {text_path}")
        return []
    except Exception as e:
        logging.error(f"Error reading text file: {e}")
        return []

    doc = nlp(text, disable=["tagger", "parser", "ner", "lemmatizer", "textcat"])
    chunks = []
    current_chunk = []

    for sent in doc.sents:
        sent_text = sent.text.strip()
        sent_tokens = count_tokens(sent_text, tokenizer)

        if sum(count_tokens(chunk, tokenizer) for chunk in current_chunk) + sent_tokens > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sent_text]
        else:
            current_chunk.append(sent_text)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def summarize_with_mlx(chunk, title):
    """Generates a summary for a chunk of text using the MLX model."""
    model, tokenizer = get_model_and_tokenizer()
    if model is None or tokenizer is None:
        logging.error("MLX model or tokenizer not loaded. Skipping summarization.")
        return None

    prompt = PROMPT.format(chunk=chunk, title=title)
    try:
        summary = generate(model, tokenizer, prompt=prompt, max_tokens=MODEL_MAX_TOKENS - count_tokens(prompt, tokenizer))
        return summary
    except Exception as e:
        logging.error(f"Error during MLX summarization: {e}")
        return None

def summarize_in_parallel(chunks, title):
    """Calls the MLX model to summarize each chunk of text in parallel."""
    summaries = []
    for chunk in chunks:
        summary = summarize_with_mlx(chunk, title)
        if summary: # only appends if summary is not None
            summaries.append(summary)
    return summaries

def save_summaries(summaries, filename_only):
    """Saves the generated summaries to a file."""
    os.makedirs(SUMMARY_DIR, exist_ok=True)  # Create directory if it doesn't exist
    summary_path = os.path.join(SUMMARY_DIR, f"{filename_only}.txt")
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            for summary in summaries:
                f.write(summary)
                f.write("\n\n")
        logging.info(f"Summaries saved to: {summary_path}")
        return summary_path
    except Exception as e:
        logging.error(f"Error saving summaries: {e}")
        return None
