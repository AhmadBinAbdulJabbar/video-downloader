import os
import re
import json
import subprocess
import tempfile
import asyncio
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Video Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "yt_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)


class VideoRequest(BaseModel):
    url: str


PLATFORM_PATTERNS = {
    "youtube": r"(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)",
    "facebook": r"(facebook\.com/(watch|reel|videos|share)|fb\.watch/|fb\.com/)",
}


def detect_platform(url: str) -> str | None:
    for platform, pattern in PLATFORM_PATTERNS.items():
        if re.search(pattern, url):
            return platform
    return None


def run_yt_dlp(args: list[str]) -> tuple[str, str, int]:
    result = subprocess.run(
        ["yt-dlp"] + args,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout, result.stderr, result.returncode


@app.post("/api/info")
async def get_video_info(req: VideoRequest):
    platform = detect_platform(req.url)
    if not platform:
        raise HTTPException(400, "Unsupported URL. Paste a YouTube or Facebook video/reel link.")

    stdout, stderr, code = run_yt_dlp([
        "--dump-json",
        "--no-playlist",
        req.url,
    ])

    if code != 0:
        raise HTTPException(400, f"Could not fetch video info: {stderr[:300]}")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        raise HTTPException(500, "Failed to parse video metadata")

    formats = []
    seen = set()

    for f in data.get("formats", []):
        ext = f.get("ext", "")
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        height = f.get("height")
        fps = f.get("fps")
        filesize = f.get("filesize") or f.get("filesize_approx")

        if vcodec == "none" or not height:
            continue

        label = f"{height}p"
        if fps and fps > 30:
            label += f" {int(fps)}fps"

        key = (height, ext)
        if key in seen:
            continue
        seen.add(key)

        formats.append({
            "format_id": f["format_id"],
            "label": label,
            "ext": ext,
            "height": height,
            "filesize": filesize,
            "has_audio": acodec != "none",
        })

    formats.sort(key=lambda x: x["height"], reverse=True)

    # Add audio-only option
    formats.append({
        "format_id": "bestaudio/best",
        "label": "Audio only (MP3)",
        "ext": "mp3",
        "height": 0,
        "filesize": None,
        "has_audio": True,
    })

    is_short = "/shorts/" in req.url
    is_reel = "/reel/" in req.url or "reel" in req.url.lower()

    return {
        "title": data.get("title", "Unknown"),
        "thumbnail": data.get("thumbnail"),
        "duration": data.get("duration"),
        "uploader": data.get("uploader"),
        "view_count": data.get("view_count"),
        "platform": platform,
        "is_short": is_short,
        "is_reel": is_reel,
        "formats": formats,
    }


@app.get("/api/download")
async def download_video(url: str, format_id: str, title: str = "video", ext: str = "mp4"):
    if not detect_platform(url):
        raise HTTPException(400, "Unsupported URL")

    safe_title = re.sub(r'[^\w\s-]', '', title)[:60].strip()
    output_path = DOWNLOAD_DIR / f"{safe_title}.%(ext)s"

    is_audio = format_id == "bestaudio/best" or ext == "mp3"

    if is_audio:
        args = [
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", str(output_path),
            "--no-playlist",
            url,
        ]
        final_ext = "mp3"
    else:
        args = [
            "-f", f"{format_id}+bestaudio[ext=m4a]/bestvideo[height<={format_id.split('p')[0] if 'p' in format_id else '9999'}]+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", str(output_path),
            "--no-playlist",
            url,
        ]
        # Simpler: use the format_id directly
        args = [
            "-f", f"{format_id}+bestaudio/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", str(output_path),
            "--no-playlist",
            url,
        ]
        final_ext = "mp4"

    stdout, stderr, code = run_yt_dlp(args)

    if code != 0:
        raise HTTPException(500, f"Download failed: {stderr[:300]}")

    # Find the actual file
    pattern = str(DOWNLOAD_DIR / f"{safe_title}.*")
    import glob
    files = glob.glob(pattern)
    if not files:
        raise HTTPException(500, "Downloaded file not found")

    file_path = Path(files[0])
    filename = quote(f"{safe_title}.{file_path.suffix.lstrip('.')}")

    def cleanup():
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass

    def file_iterator():
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
        finally:
            cleanup()

    media_type = "audio/mpeg" if final_ext == "mp3" else "video/mp4"
    return StreamingResponse(
        file_iterator(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file_path.stat().st_size),
        },
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
