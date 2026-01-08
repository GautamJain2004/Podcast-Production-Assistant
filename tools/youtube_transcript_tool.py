"""
YouTube Transcript Extraction Tool

Extracts transcripts from YouTube videos for research purposes.
"""

import logging
from typing import Optional, Dict, Any, List
import re

logger = logging.getLogger(__name__)

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False
    logger.warning("youtube-transcript-api not installed. Install with: pip install youtube-transcript-api")


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract video ID from various YouTube URL formats.
    
    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    """
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # If no pattern matches, assume it's already a video ID
    if len(url) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url
    
    return None


def get_youtube_transcript(video_url: str, languages: List[str] = None) -> Dict[str, Any]:
    """
    Get transcript from a YouTube video.
    
    Args:
        video_url: YouTube video URL or video ID
        languages: List of language codes to try (default: ['en'])
    
    Returns:
        Dict with 'success', 'transcript', 'video_id', 'title', and 'error' keys
    """
    if not YOUTUBE_AVAILABLE:
        return {
            "success": False,
            "error": "youtube-transcript-api not installed",
            "transcript": "",
            "video_id": None
        }
    
    if languages is None:
        languages = ['en']
    
    video_id = extract_video_id(video_url)
    if not video_id:
        return {
            "success": False,
            "error": f"Could not extract video ID from: {video_url}",
            "transcript": "",
            "video_id": None
        }
    
    try:
        # Get transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        
        # Combine all text segments
        full_transcript = " ".join([entry['text'] for entry in transcript_list])
        
        # Get video metadata if possible
        try:
            from pytube import YouTube
            yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
            title = yt.title
        except:
            title = f"Video {video_id}"
        
        return {
            "success": True,
            "transcript": full_transcript,
            "video_id": video_id,
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "segments": len(transcript_list),
            "error": None
        }
        
    except TranscriptsDisabled:
        return {
            "success": False,
            "error": "Transcripts are disabled for this video",
            "transcript": "",
            "video_id": video_id
        }
    except NoTranscriptFound:
        return {
            "success": False,
            "error": f"No transcript found in languages: {languages}",
            "transcript": "",
            "video_id": video_id
        }
    except Exception as e:
        logger.error(f"Error getting YouTube transcript: {e}")
        return {
            "success": False,
            "error": str(e),
            "transcript": "",
            "video_id": video_id
        }


def search_youtube_videos(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search for YouTube videos related to a query.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
    
    Returns:
        List of dicts with 'video_id', 'title', 'url' keys
    """
    try:
        from googleapiclient.discovery import build
        from config.settings import get_settings
        
        settings = get_settings()
        api_key = settings.youtube_api_key
        
        if not api_key:
            logger.warning("YouTube API key not configured")
            return []
        
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        request = youtube.search().list(
            q=query,
            part='snippet',
            type='video',
            maxResults=max_results,
            relevanceLanguage='en'
        )
        
        response = request.execute()
        
        results = []
        for item in response.get('items', []):
            video_id = item['id']['videoId']
            title = item['snippet']['title']
            results.append({
                'video_id': video_id,
                'title': title,
                'url': f'https://www.youtube.com/watch?v={video_id}'
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error searching YouTube: {e}")
        return []
