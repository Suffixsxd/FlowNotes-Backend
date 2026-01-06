# Flow Backend - YouTube Transcription API

Python Flask backend that uses AssemblyAI to transcribe YouTube videos.

## Setup

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. The `.env` file is already configured with your API key.

3. Run the server:
```bash
python app.py
```

The server will start on `http://localhost:5000`

## API Endpoints

### Health Check
```
GET /api/health
```

### Transcribe YouTube Video
```
POST /api/transcribe-youtube
Content-Type: application/json

{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

Response:
```json
{
    "success": true,
    "transcript": "Full video transcript...",
    "title": "Video Title",
    "videoId": "VIDEO_ID"
}
```

## Deployment

Deploy this backend separately to a Python-compatible host like:
- Railway
- Render
- Fly.io
- Heroku

Then set `VITE_BACKEND_URL` in the frontend's `.env.local` to your deployed URL.

## Requirements

- Python 3.9+
- yt-dlp (installed via pip, but may need ffmpeg on some systems)
