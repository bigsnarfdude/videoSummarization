#!/usr/bin/env python3
"""
Process all videos from BIRS 2025 archive
Simple automation without database complexity
"""
import requests
import re
from bs4 import BeautifulSoup
from pathlib import Path
import json
from process_video import process_video
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def scrape_workshops(year: int) -> list:
    """Get all workshop IDs for a given year"""
    url = f"https://videos.birs.ca/{year}/"

    logger.info(f"Scraping workshops from {url}")
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all directory links (format: 25w5318/)
    workshops = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        match = re.match(r'(\d{2}w\d{4})/', href)
        if match:
            workshops.append(match.group(1))

    logger.info(f"Found {len(workshops)} workshops")
    return workshops


def scrape_videos(year: int, workshop_id: str) -> list:
    """Get all videos for a workshop"""
    url = f"https://videos.birs.ca/{year}/{workshop_id}/"

    logger.info(f"Scraping videos from {workshop_id}")
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all .mp4 files
    videos = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.endswith('.mp4'):
            # Parse filename: 202507210900-Walton.mp4
            match = re.match(r'(\d{12})-(.+)\.mp4', href)
            if match:
                timestamp = match.group(1)
                speaker = match.group(2)

                videos.append({
                    'url': url + href,
                    'workshop': workshop_id,
                    'timestamp': timestamp,
                    'speaker': speaker,
                    'basename': f"{workshop_id}_{timestamp}_{speaker}"
                })

    return videos


def load_progress():
    """Load processing progress from JSON file"""
    progress_file = Path('data/progress.json')
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {'processed': [], 'failed': []}


def save_progress(progress):
    """Save processing progress"""
    progress_file = Path('data/progress.json')
    progress_file.parent.mkdir(exist_ok=True)

    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)


def process_archive(year: int = 2025, limit: int = None, skip_existing: bool = True):
    """
    Process all videos from archive

    Args:
        year: Year to process (default: 2025)
        limit: Max number of videos to process (None = all)
        skip_existing: Skip videos already processed
    """
    progress = load_progress()

    # Step 1: Discover all videos
    logger.info(f"Discovering videos from {year}...")
    workshops = scrape_workshops(year)

    all_videos = []
    for workshop_id in workshops:
        try:
            videos = scrape_videos(year, workshop_id)
            all_videos.extend(videos)
        except Exception as e:
            logger.error(f"Error scraping {workshop_id}: {e}")

    logger.info(f"Total videos discovered: {len(all_videos)}")

    # Filter out already processed
    if skip_existing:
        processed_basenames = set(progress['processed'])
        all_videos = [v for v in all_videos if v['basename'] not in processed_basenames]
        logger.info(f"Videos to process (after filtering): {len(all_videos)}")

    # Apply limit
    if limit:
        all_videos = all_videos[:limit]
        logger.info(f"Processing first {limit} videos")

    # Step 2: Process each video
    for i, video in enumerate(all_videos, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {i}/{len(all_videos)}: {video['basename']}")
        logger.info(f"{'='*60}")

        try:
            result = process_video(video['url'], video['basename'])

            if result['status'] == 'success':
                progress['processed'].append(video['basename'])
                logger.info(f"✅ Success: {video['basename']}")
            else:
                progress['failed'].append({
                    'basename': video['basename'],
                    'error': result.get('error', 'Unknown error')
                })
                logger.error(f"❌ Failed: {video['basename']}")

            # Save progress after each video
            save_progress(progress)

        except Exception as e:
            logger.error(f"❌ Unexpected error processing {video['basename']}: {e}")
            progress['failed'].append({
                'basename': video['basename'],
                'error': str(e)
            })
            save_progress(progress)

    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"PROCESSING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total processed: {len(progress['processed'])}")
    logger.info(f"Total failed: {len(progress['failed'])}")

    if progress['failed']:
        logger.info(f"\nFailed videos:")
        for failed in progress['failed'][-10:]:  # Show last 10
            logger.info(f"  - {failed['basename']}: {failed['error']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Process BIRS video archive')
    parser.add_argument('--year', type=int, default=2025, help='Year to process (default: 2025)')
    parser.add_argument('--limit', type=int, help='Max videos to process (default: all)')
    parser.add_argument('--no-skip', action='store_true', help='Reprocess already completed videos')

    args = parser.parse_args()

    process_archive(
        year=args.year,
        limit=args.limit,
        skip_existing=not args.no_skip
    )
