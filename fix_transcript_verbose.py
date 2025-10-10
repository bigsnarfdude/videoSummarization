#!/usr/bin/env python3
"""
Verbose transcript correction using comprehensive math terminology database
Fixes common ASR errors while preserving mathematical content
"""
import sys
import json
import requests
from pathlib import Path
import re
from collections import defaultdict

def load_corrections(json_path='math_corrections.json'):
    """Load comprehensive corrections from JSON file"""
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Flatten all categories into single dict
    all_corrections = {}
    for category, corrections in data['categories'].items():
        all_corrections.update(corrections)

    return all_corrections

def apply_comprehensive_corrections(text, corrections_dict):
    """Apply regex-based corrections with detailed reporting"""
    corrected = text
    changes_by_category = defaultdict(list)
    total_fixes = 0

    # Sort by length (longest first) to avoid partial replacements
    sorted_patterns = sorted(corrections_dict.items(),
                            key=lambda x: len(x[0]),
                            reverse=True)

    for pattern, replacement in sorted_patterns:
        # Create word-boundary regex
        regex_pattern = r'\b' + re.escape(pattern) + r'\b'

        # Find all matches before replacement
        matches = list(re.finditer(regex_pattern, corrected, re.IGNORECASE))

        if matches:
            count = len(matches)
            total_fixes += count

            # Get sample of matched text
            sample = matches[0].group(0) if matches else pattern

            # Perform replacement
            corrected = re.sub(regex_pattern, replacement, corrected, flags=re.IGNORECASE)

            changes_by_category['corrections'].append({
                'pattern': pattern,
                'replacement': replacement,
                'count': count,
                'sample': sample
            })

    return corrected, changes_by_category, total_fixes

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

Corrected transcript (preserve speaker's voice, only fix errors):")
"""

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

def add_sentence_breaks(text):
    """Add sentence breaks for readability"""
    # Split very long sentences (>150 words)
    sentences = text.split('. ')
    fixed_sentences = []

    for sent in sentences:
        words = sent.split()
        if len(words) > 150:
            # Try to split at natural breaks (conjunctions)
            for break_word in [' And ', ' But ', ' So ', ' Now ', ' Okay ', ' Well ']:
                if break_word in sent:
                    parts = sent.split(break_word, 1)
                    sent = parts[0] + '.' + break_word + parts[1]
                    break
        fixed_sentences.append(sent)

    return '. '.join(fixed_sentences)

def process_transcript(input_path, output_path, use_llm=False, corrections_file='math_corrections.json'):
    """Process transcript with comprehensive corrections"""
    print(f"\n{'='*80}")
    print(f"VERBOSE CORRECTION: {input_path.name}")
    print(f"{'='*80}")

    # Read original
    with open(input_path, 'r', encoding='utf-8') as f:
        original = f.read()

    original_words = len(original.split())
    print(f"Original: {original_words:,} words")

    # Load comprehensive corrections
    print(f"\n[Step 1] Loading corrections from {corrections_file}...")
    corrections = load_corrections(corrections_file)
    print(f"  Loaded {len(corrections)} correction patterns")

    # Apply comprehensive regex corrections
    print("\n[Step 2] Applying comprehensive corrections...")
    corrected, changes, total_fixes = apply_comprehensive_corrections(original, corrections)

    if total_fixes > 0:
        print(f"  ✅ Applied {total_fixes} corrections:")
        for change in changes['corrections']:
            print(f"     • {change['sample']} → {change['replacement']} ({change['count']}x)")
    else:
        print("  ℹ️  No regex corrections needed")

    # LLM polishing (optional, slower)
    if use_llm:
        print("\n[Step 3] LLM polishing (this takes ~5-10 min)...")
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
        print("\n[Step 3] LLM polishing: SKIPPED (use --llm to enable)")

    # Add sentence breaks
    print("\n[Step 4] Adding sentence breaks...")
    corrected = add_sentence_breaks(corrected)

    corrected_words = len(corrected.split())
    print(f"  Final: {corrected_words:,} words")

    # Save corrected version
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(corrected)

    print(f"\n✅ Saved to: {output_path}")

    # Show statistics
    print(f"\n{'='*80}")
    print("CORRECTION STATISTICS")
    print(f"{'='*80}")
    print(f"Total corrections applied: {total_fixes}")
    print(f"Word count change: {original_words:,} → {corrected_words:,} ({corrected_words - original_words:+,})")
    print(f"Correction rate: {(total_fixes/original_words*100):.2f}% of words")

    # Show sample comparison
    print(f"\n{'='*80}")
    print("BEFORE (first 500 chars):")
    print(original[:500])
    print(f"\n{'='*80}")
    print("AFTER (first 500 chars):")
    print(corrected[:500])
    print(f"{'='*80}\n")

    return total_fixes, changes

def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_transcript_verbose.py <transcript.txt> [--llm] [--corrections <file.json>]")
        print("\nOptions:")
        print("  --llm                  Enable LLM polishing (slow but thorough)")
        print("  --corrections <file>   Use custom corrections JSON (default: math_corrections.json)")
        print("\nExample:")
        print("  python fix_transcript_verbose.py files/transcripts/25w5318_202507210900_Walton.txt")
        print("  python fix_transcript_verbose.py files/transcripts/25w5318_202507210900_Walton.txt --llm")
        print("  python fix_transcript_verbose.py transcript.txt --corrections custom_math.json")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    use_llm = '--llm' in sys.argv

    # Check for custom corrections file
    corrections_file = 'math_corrections.json'
    if '--corrections' in sys.argv:
        idx = sys.argv.index('--corrections')
        if idx + 1 < len(sys.argv):
            corrections_file = sys.argv[idx + 1]

    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        sys.exit(1)

    # Check if corrections file exists
    if not Path(corrections_file).exists():
        print(f"❌ Corrections file not found: {corrections_file}")
        print(f"   Please create math_corrections.json or specify --corrections <file>")
        sys.exit(1)

    # Output to same name with _corrected.txt
    output_path = input_path.parent / f"{input_path.stem}_corrected.txt"

    total_fixes, changes = process_transcript(input_path, output_path, use_llm, corrections_file)

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
