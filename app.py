"""
Flow Backend API - YouTube Transcription with AssemblyAI
Uses direct HTTP requests instead of SDK for Python 3.14 compatibility
Downloads audio locally then uploads to AssemblyAI
"""

import os
import re
import time
import tempfile
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# Load environment variables
load_dotenv()

# AssemblyAI configuration
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
ASSEMBLYAI_BASE_URL = "https://api.assemblyai.com"

app = Flask(__name__)
# Allow CORS for all origins (temporarily for debugging connection issues)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/", methods=["GET"])
def index():
    """Root endpoint to verify server is running."""
    return "Flow Backend is running! 🚀"


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def download_youtube_audio(video_url: str) -> str:
    """Download YouTube audio to a temp file and return the file path."""
    import subprocess
    
    # Create temp file for audio
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, f"yt_audio_{int(time.time())}.mp3")
    
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "-f", "bestaudio",
                "-x",  # Extract audio
                "--audio-format", "mp3",
                "-o", output_path,
                "--no-warnings",
                video_url
            ],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout for download
        )
        
        if result.returncode != 0:
            raise Exception(f"yt-dlp error: {result.stderr}")
        
        # yt-dlp may add extension, check for the file
        if os.path.exists(output_path):
            return output_path
        # Check with .mp3 extension added
        if os.path.exists(output_path + ".mp3"):
            return output_path + ".mp3"
        # Check for webm (original format)
        base_path = output_path.rsplit(".", 1)[0]
        for ext in [".mp3", ".m4a", ".webm", ".opus"]:
            if os.path.exists(base_path + ext):
                return base_path + ext
            
        raise Exception("Audio file not found after download")
        
    except subprocess.TimeoutExpired:
        raise Exception("Timeout while downloading video")
    except FileNotFoundError:
        raise Exception("yt-dlp not installed. Install with: pip install yt-dlp")


def get_video_title(video_url: str) -> str:
    """Get YouTube video title using yt-dlp."""
    import subprocess
    
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--get-title",
                "--no-warnings",
                video_url
            ],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "YouTube Video"
        
    except Exception:
        return "YouTube Video"


def upload_to_assemblyai(file_path: str) -> str:
    """Upload audio file to AssemblyAI and return the upload URL."""
    headers = {
        "authorization": ASSEMBLYAI_API_KEY
    }
    
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{ASSEMBLYAI_BASE_URL}/v2/upload",
            headers=headers,
            data=f
        )
    
    if response.status_code != 200:
        raise Exception(f"Failed to upload audio: {response.text}")
    
    return response.json()["upload_url"]


def transcribe_audio_with_assemblyai(audio_url: str) -> str:
    """Transcribe audio using AssemblyAI's REST API directly."""
    headers = {
        "authorization": ASSEMBLYAI_API_KEY,
        "content-type": "application/json"
    }
    
    # Submit transcription request
    data = {
        "audio_url": audio_url
    }
    
    response = requests.post(
        f"{ASSEMBLYAI_BASE_URL}/v2/transcript",
        json=data,
        headers=headers
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to submit transcription: {response.text}")
    
    transcript_id = response.json()["id"]
    polling_endpoint = f"{ASSEMBLYAI_BASE_URL}/v2/transcript/{transcript_id}"
    
    # Poll for completion
    max_attempts = 120  # Max 6 minutes of polling (for longer videos)
    for _ in range(max_attempts):
        result = requests.get(polling_endpoint, headers=headers).json()
        
        if result["status"] == "completed":
            return result["text"]
        elif result["status"] == "error":
            raise Exception(f"Transcription failed: {result.get('error', 'Unknown error')}")
        
        time.sleep(3)
    
    raise Exception("Transcription timed out")


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "flow-backend"})


@app.route("/api/transcribe-youtube", methods=["POST"])
def transcribe_youtube():
    """
    Transcribe a YouTube video using AssemblyAI.
    
    Request body:
    {
        "url": "https://www.youtube.com/watch?v=..."
    }
    
    Response:
    {
        "success": true,
        "transcript": "...",
        "title": "Video Title",
        "videoId": "..."
    }
    """
    audio_file_path = None
    
    try:
        data = request.get_json()
        
        if not data or "url" not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'url' in request body"
            }), 400
        
        url = data["url"]
        video_id = extract_video_id(url)
        
        if not video_id:
            return jsonify({
                "success": False,
                "error": "Invalid YouTube URL"
            }), 400
        
        # Get video title
        video_title = get_video_title(url)
        
        # Download audio locally
        print(f"[Transcribe] Downloading audio for video: {video_id}")
        audio_file_path = download_youtube_audio(url)
        print(f"[Transcribe] Downloaded to: {audio_file_path}")
        
        # Upload to AssemblyAI
        print(f"[Transcribe] Uploading to AssemblyAI...")
        upload_url = upload_to_assemblyai(audio_file_path)
        print(f"[Transcribe] Uploaded, starting transcription...")
        
        # Transcribe with AssemblyAI
        transcript_text = transcribe_audio_with_assemblyai(upload_url)
        
        print(f"[Transcribe] Transcription complete, {len(transcript_text or '')} chars")
        
        return jsonify({
            "success": True,
            "transcript": transcript_text,
            "title": video_title,
            "videoId": video_id
        })
        
    except Exception as e:
        print(f"[Transcribe] Error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
    finally:
        # Clean up temp file
        if audio_file_path and os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
            except:
                pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Flow Backend starting on port {port}")
    print(f"📺 YouTube transcription endpoint: POST /api/transcribe-youtube")
    app.run(host="0.0.0.0", port=port, debug=True)
