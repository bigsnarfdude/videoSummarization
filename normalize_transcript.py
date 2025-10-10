#!/usr/bin/env python3
"""
Normalize and clean transcripts before summarization
- Remove repetitive phrases
- Fix common transcription errors
- Remove filler words
- Clean up formatting
"""
import re
import sys

def normalize_transcript(text):
    """Clean and normalize transcript text"""

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove repetitive phrases (same phrase repeated 2+ times in a row)
    # e.g., "pushing this a little further pushing this a little further" -> "pushing this a little further"
    words = text.split()
    cleaned_words = []
    i = 0

    while i < len(words):
        # Look for repetitions of 3-15 word phrases
        found_repetition = False
        for phrase_len in range(15, 2, -1):  # Start with longer phrases
            if i + phrase_len * 2 <= len(words):
                phrase1 = ' '.join(words[i:i+phrase_len])
                phrase2 = ' '.join(words[i+phrase_len:i+phrase_len*2])

                if phrase1.lower() == phrase2.lower():
                    # Found repetition, add once and skip
                    cleaned_words.extend(words[i:i+phrase_len])
                    i += phrase_len * 2
                    found_repetition = True
                    break

        if not found_repetition:
            cleaned_words.append(words[i])
            i += 1

    text = ' '.join(cleaned_words)

    # Remove common filler words and phrases
    fillers = [
        r'\bokay\b',
        r'\buh\b',
        r'\bum\b',
        r'\blike\b(?=\s+[,.])',  # "like," at end of phrase
        r'\byou know\b',
        r'\bI mean\b',
        r'\bright\b(?=\s*[,.])',  # "right," as filler
    ]

    for filler in fillers:
        text = re.sub(filler, '', text, flags=re.IGNORECASE)

    # Remove stuttering (repeated single words)
    text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)

    # Clean up punctuation spacing
    text = re.sub(r'\s+([,.])', r'\1', text)
    text = re.sub(r'([,.])\s*([,.])', r'\1', text)

    # Remove excessive spaces again
    text = re.sub(r'\s+', ' ', text)

    # Remove nonsense fragments at the end (common in Q&A)
    # Look for patterns like "Thank you. Thank you. Thank you." repeated
    lines = text.split('.')
    cleaned_lines = []
    seen_recent = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this line was recently seen (within last 5 lines)
        if line.lower() in seen_recent and len(line.split()) < 10:
            continue  # Skip repetitive short phrases

        cleaned_lines.append(line)
        seen_recent.add(line.lower())

        # Keep only last 5 lines in memory
        if len(seen_recent) > 5:
            seen_recent = set(list(seen_recent)[-5:])

    text = '. '.join(cleaned_lines)

    # Final cleanup
    text = text.strip()
    if text and not text.endswith('.'):
        text += '.'

    return text


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python normalize_transcript.py <input.txt> <output.txt>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    print(f"Reading: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        original = f.read()

    print(f"Original: {len(original)} chars, {len(original.split())} words")

    print("Normalizing...")
    normalized = normalize_transcript(original)

    print(f"Normalized: {len(normalized)} chars, {len(normalized.split())} words")
    print(f"Reduction: {100*(1-len(normalized)/len(original)):.1f}%")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(normalized)

    print(f"\n✅ Saved to: {output_path}")

    print(f"\nFirst 500 chars of normalized text:")
    print(normalized[:500])
