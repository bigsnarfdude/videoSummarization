#!/usr/bin/env python3
"""
Comprehensive quality review for transcripts and summaries
"""
import sys
from pathlib import Path
import re

def check_transcript_quality(text_path):
    """Analyze transcript for common issues"""
    with open(text_path, 'r', encoding='utf-8') as f:
        content = f.read()

    issues = []

    # Check for common transcription errors
    common_errors = {
        'five-dimensional': 'finite-dimensional',
        'hofland': 'Hopf algebra',
        'model diffusion': 'monoidal fusion',
        'fine parallel': 'finite parallel',
        'co-in': 'coend',
    }

    for wrong, correct in common_errors.items():
        if wrong in content.lower():
            count = len(re.findall(re.escape(wrong), content, re.IGNORECASE))
            issues.append(f"Found '{wrong}' {count} times (should be '{correct}')")

    # Check for excessive filler words
    fillers = ['um ', 'uh ', 'like ', ' all ']
    filler_counts = {f: content.lower().count(f) for f in fillers}
    excessive_fillers = {f: c for f, c in filler_counts.items() if c > 50}
    if excessive_fillers:
        issues.append(f"Excessive filler words: {excessive_fillers}")

    # Check for missing punctuation (long runs without periods)
    sentences = content.split('.')
    long_sentences = [s for s in sentences if len(s.split()) > 100]
    if long_sentences:
        issues.append(f"Found {len(long_sentences)} very long sentences (>100 words)")

    # Check capitalization
    lines = content.split('\n')
    uncapitalized = [l for l in lines if l and l[0].islower() and len(l) > 10]
    if len(uncapitalized) > 5:
        issues.append(f"Many uncapitalized sentences: {len(uncapitalized)}")

    return issues

def check_summary_quality(summary_path):
    """Analyze summary for quality issues"""
    with open(summary_path, 'r', encoding='utf-8') as f:
        content = f.read()

    issues = []

    # Check for "Main takeaway" or similar conclusion
    if not any(x in content.lower() for x in ['main takeaway', 'main message', 'key takeaway']):
        issues.append("Missing 'Main takeaway' conclusion")

    # Check for bullet points
    if content.count('•') < 3 and content.count('-') < 3:
        issues.append("Very few bullet points - may not be formatted correctly")

    # Check for mathematical content preservation
    if '\\' in content:  # LaTeX math
        latex_count = content.count('\\')
        if latex_count > 0:
            issues.append(f"Contains {latex_count} LaTeX commands (good for math)")

    # Check length
    word_count = len(content.split())
    if word_count < 200:
        issues.append(f"Very short summary: only {word_count} words")
    elif word_count > 5000:
        issues.append(f"Very long summary: {word_count} words")

    return issues

def main():
    transcript_dir = Path('files/transcripts')
    summary_dir = Path('files/summaries')

    print("=" * 80)
    print("TRANSCRIPT QUALITY REVIEW")
    print("=" * 80)

    for transcript in sorted(transcript_dir.glob('*.txt')):
        if transcript.stat().st_size == 0:
            print(f"\n❌ {transcript.name}: EMPTY FILE")
            continue

        issues = check_transcript_quality(transcript)

        if issues:
            print(f"\n⚠️  {transcript.name}:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            word_count = len(transcript.read_text().split())
            print(f"✅ {transcript.name}: {word_count} words, no issues")

    print("\n" + "=" * 80)
    print("SUMMARY QUALITY REVIEW")
    print("=" * 80)

    for summary in sorted(summary_dir.glob('*.txt')):
        issues = check_summary_quality(summary)

        if issues:
            print(f"\n⚠️  {summary.name}:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            word_count = len(summary.read_text().split())
            print(f"✅ {summary.name}: {word_count} words, no issues")

    print("\n" + "=" * 80)
    print("MATCHING CHECK")
    print("=" * 80)

    # Check that every transcript has a summary
    transcripts = {f.stem for f in transcript_dir.glob('*.txt') if f.stat().st_size > 0}
    summaries = {f.stem.replace('_summary', '') for f in summary_dir.glob('*.txt')}

    missing_summaries = transcripts - summaries
    if missing_summaries:
        print(f"\n⚠️  Transcripts missing summaries: {missing_summaries}")
    else:
        print(f"✅ All {len(transcripts)} transcripts have summaries")

if __name__ == '__main__':
    main()
