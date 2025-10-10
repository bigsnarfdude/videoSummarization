#!/usr/bin/env python3
"""
Intelligent transcript correction using LLM
Fixes common ASR errors while preserving mathematical content
"""
import sys
import requests
from pathlib import Path
import re

# Common ASR error patterns for mathematical lectures
CORRECTIONS = {
    # Whisper homophone errors
    r'\bfive-dimensional\b': 'finite-dimensional',
    r'\bfive dimensional\b': 'finite dimensional',
    r'\bhofland\b': 'Hopf algebra',
    r'\bco-in\b': 'coend',
    r'\bco-ins\b': 'coends',
    r'\bfine parallel\b': 'finite parallel',
    r'\bmodel diffusion\b': 'monoidal fusion',
    r'\bcat theory\b': 'category theory',
    r'\btensor product\b': 'tensor product',  # Already correct but check context
}

def apply_simple_corrections(text):
    """Apply regex-based corrections for known errors"""
    corrected = text
    changes = []

    for pattern, replacement in CORRECTIONS.items():
        matches = re.findall(pattern, corrected, re.IGNORECASE)
        if matches:
            changes.append(f"Fixed {len(matches)}x: {matches[0]} → {replacement}")
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)

    return corrected, changes

def split_into_chunks(text, max_words=500):
    """Split text into manageable chunks for LLM processing"""
    words = text.split()
    chunks = []

    for i in range(0, len(words), max_words):
        chunk = ' '.join(words[i:i+max_words])
        chunks.append(chunk)

    return chunks

def llm_polish_chunk(chunk, context="mathematical lecture"):
    """Use LLM to polish a transcript chunk"""
    prompt = f"""You are an expert editor for mathematical lecture transcripts.

Fix the following issues ONLY:
1. Correct obvious ASR/transcription errors (homophones, misheard technical terms)
2. Add paragraph breaks at natural topic changes
3. Fix capitalization of proper names and technical terms
4. Preserve ALL mathematical content exactly as spoken

DO NOT:
- Change the speaker's words or meaning
- Remove filler words (um, uh) - keep them
- Rewrite sentences - only fix errors
- Add content not in the original

Context: This is a {context} transcript.

Original transcript:
{chunk}

Corrected transcript (preserve speaker's voice, only fix errors):"""

    try:
        response = requests.post('http://localhost:11434/api/generate', json={
            'model': 'gpt-oss:20b',
            'prompt': prompt,
            'stream': False,
            'keep_alive': 0
        }, timeout=300)

        if response.status_code == 200:
            return response.json()['response']
        else:
            print(f"⚠️  LLM failed with status {response.status_code}, using original")
            return chunk
    except Exception as e:
        print(f"⚠️  LLM error: {e}, using original")
        return chunk

def process_transcript(input_path, output_path, use_llm=False):
    """Process transcript with corrections"""
    print(f"\n{'='*80}")
    print(f"Processing: {input_path.name}")
    print(f"{'='*80}")

    # Read original
    with open(input_path, 'r', encoding='utf-8') as f:
        original = f.read()

    original_words = len(original.split())
    print(f"Original: {original_words} words")

    # Step 1: Apply simple regex corrections
    print("\n[Step 1] Applying regex corrections...")
    corrected, changes = apply_simple_corrections(original)

    if changes:
        print("Changes made:")
        for change in changes:
            print(f"  ✓ {change}")
    else:
        print("  No regex corrections needed")

    # Step 2: LLM polishing (optional, slower)
    if use_llm:
        print("\n[Step 2] LLM polishing (this takes ~5-10 min)...")
        chunks = split_into_chunks(corrected, max_words=500)
        print(f"  Processing {len(chunks)} chunks...")

        polished_chunks = []
        for i, chunk in enumerate(chunks, 1):
            print(f"  Chunk {i}/{len(chunks)}...", end=' ', flush=True)
            polished = llm_polish_chunk(chunk)
            polished_chunks.append(polished)
            print("✓")

        corrected = '\n\n'.join(polished_chunks)
        print("  LLM polishing complete")
    else:
        print("\n[Step 2] LLM polishing: SKIPPED (use --llm to enable)")

    # Step 3: Add sentence breaks for readability
    print("\n[Step 3] Adding sentence breaks...")
    # Split very long sentences (>150 words)
    sentences = corrected.split('. ')
    fixed_sentences = []

    for sent in sentences:
        words = sent.split()
        if len(words) > 150:
            # Try to split at natural breaks (conjunctions)
            # Insert period before: "And", "But", "So", "Now", "Okay"
            for break_word in [' And ', ' But ', ' So ', ' Now ', ' Okay ', ' Well ']:
                if break_word in sent:
                    parts = sent.split(break_word, 1)
                    sent = parts[0] + '.' + break_word + parts[1]
                    break
        fixed_sentences.append(sent)

    corrected = '. '.join(fixed_sentences)

    corrected_words = len(corrected.split())
    print(f"Final: {corrected_words} words")

    # Save corrected version
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(corrected)

    print(f"\n✅ Saved to: {output_path}")

    # Show sample
    print(f"\n{'='*80}")
    print("BEFORE (first 500 chars):")
    print(original[:500])
    print(f"\n{'='*80}")
    print("AFTER (first 500 chars):")
    print(corrected[:500])
    print(f"{'='*80}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_transcript.py <transcript.txt> [--llm]")
        print("\nOptions:")
        print("  --llm    Enable LLM polishing (slow but thorough)")
        print("\nExample:")
        print("  python fix_transcript.py files/transcripts/25w5318_202507210900_Walton.txt")
        print("  python fix_transcript.py files/transcripts/25w5318_202507210900_Walton.txt --llm")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    use_llm = '--llm' in sys.argv

    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        sys.exit(1)

    # Output to same name with .corrected.txt
    output_path = input_path.parent / f"{input_path.stem}_corrected.txt"

    process_transcript(input_path, output_path, use_llm=use_llm)

    print(f"\n{'='*80}")
    print("NEXT STEPS:")
    print(f"{'='*80}")
    print(f"1. Review corrected transcript: {output_path}")
    print(f"2. If satisfied, replace original:")
    print(f"   mv {output_path} {input_path}")
    print(f"3. Regenerate summary from corrected transcript:")
    print(f"   python regenerate_summary.py {input_path}")

if __name__ == '__main__':
    main()
