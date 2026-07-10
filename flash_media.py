#!/usr/bin/env python3
"""
Flash Media - Universal Media Downloader
=========================================

A dark-mode desktop application for downloading video and audio from thousands
of sites (YouTube, Vimeo, Twitter, Twitch, etc.) powered by yt-dlp, with
automatic HD video+audio merging via FFmpeg.

Tech stack:
    - GUI:      CustomTkinter (modern dark Tk widgets)
    - Engine:   yt-dlp (extraction + download)
    - Merger:   FFmpeg (via subprocess, auto-located on the system)
    - Async:    threading (GUI stays 100% responsive)

Run:
    python flash_media.py

Requires: customtkinter, yt-dlp, Pillow  AND  a system ffmpeg binary.
See requirements.txt and the README block at the bottom of this file.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import threading
import time
import traceback
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

try:
    import customtkinter as ctk
    from PIL import Image, ImageTk
except Exception as import_err:  # pragma: no cover - environment guard
    raise SystemExit(
        "Flash Media requires customtkinter and Pillow.\n"
        "Install them with:  pip install customtkinter yt-dlp Pillow\n"
        f"(Original import error: {import_err})"
    )

import yt_dlp

# =====================================================================
# THEME
# =====================================================================
# Dark Mode palette exactly per spec, with a full ramp of derived shades
# so the UI has proper visual hierarchy (design requirement).
THEME = {
    "bg": "#1A1A1A",          # main background
    "bg_elevated": "#222629", # cards / panels
    "surface": "#2A2F36",     # inputs, dropdowns
    "accent": "#00ADB5",      # primary accent (teal)
    "accent_hover": "#00C9D2",
    "accent_pressed": "#008B92",
    "secondary": "#393E46",   # secondary accent (slate)
    "secondary_hover": "#4A5059",
    "text": "#EEEEEE",        # primary text
    "text_muted": "#9AA0A6",  # secondary text
    "success": "#3DDC84",
    "warning": "#FFB74D",
    "error": "#FF5252",
    "border": "#3A3F47",
}

FONT_FAMILY = "Segoe UI"  # CustomTkinter falls back gracefully on non-Windows


# =====================================================================
# DOWNLOAD ENGINE
# =====================================================================
@dataclass
class StreamFormat:
    """A single selectable media stream/format returned by extraction."""
    label: str            # human-readable, e.g. "1080p (MP4)"
    format_id: str        # yt-dlp format id / selector string
    is_audio_only: bool = False
    needs_merge: bool = False       # True when video+audio must be muxed
    ext: str = "mp4"
    filesize_approx: Optional[int] = None  # bytes, best-effort


@dataclass
class MediaInfo:
    """Aggregated metadata for a parsed URL."""
    title: str = ""
    duration: int = 0
    thumbnail_url: str = ""
    uploader: str = ""
    webpage_url: str = ""
    streams: List[StreamFormat] = field(default_factory=list)
    raw_info: Dict[str, Any] = field(default_factory=dict)


class DownloadEngine:
    """
    Wraps yt-dlp for extraction + download, and FFmpeg for merging.
    All public methods run synchronously and are meant to be called from a
    worker thread so the GUI never blocks.
    """

    # Resolutions we surface as discrete choices (height -> label).
    QUALITY_LADDER = [2160, 1440, 1080, 720, 480, 360, 240, 144]

    def __init__(self, ffmpeg_location: Optional[str] = None) -> None:
        self._ffmpeg_path = ffmpeg_location or self._locate_ffmpeg()

    # ---- FFmpeg ----------------------------------------------------------
    @staticmethod
    def _locate_ffmpeg() -> str:
        path = shutil.which("ffmpeg")
        if path:
            return path
        # Common extra locations on Windows/macOS portable installs.
        for candidate in (
            "ffmpeg",
            os.path.join(os.getcwd(), "ffmpeg"),
            os.path.join(os.getcwd(), "bin", "ffmpeg"),
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg",
        ):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return "ffmpeg"  # fall back to bare name; merge step will surface error

    @property
    def ffmpeg_available(self) -> bool:
        try:
            subprocess.run(
                [self._ffmpeg_path, "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    # ---- Extraction ------------------------------------------------------
    def extract(self, url: str, on_log: Optional[Callable[[str], None]] = None
                ) -> MediaInfo:
        """
        Parse a URL and return aggregated MediaInfo.
        Raises ValueError on invalid/empty URLs; raises yt-dlp exceptions
        on extraction failures (caller handles).
        """
        if not url or not url.strip():
            raise ValueError("No URL provided.")
        url = url.strip()
        if not self._looks_like_url(url):
            raise ValueError("That doesn't look like a valid URL.")

        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "ffmpeg_location": self._ffmpeg_path,
            "extract_flat": False,
            "socket_timeout": 30,
            "retries": 3,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise RuntimeError("yt-dlp returned no information for this link.")

        # Playlists: focus on the first entry to keep the UX simple.
        if "entries" in info:
            entries = [e for e in info["entries"] if e]
            if not entries:
                raise RuntimeError("This playlist appears to be empty.")
            if on_log:
                on_log(f"Playlist detected ({len(entries)} items). "
                       "Showing the first entry only.")
            info = entries[0]
            # Flatten nested entries (some extractors nest twice).
            while isinstance(info, dict) and "entries" in info:
                nested = [e for e in info["entries"] if e]
                if not nested:
                    break
                info = nested[0]

        return self._build_media_info(info)

    def _build_media_info(self, info: Dict[str, Any]) -> MediaInfo:
        title = info.get("title") or info.get("id") or "Untitled"
        duration = int(info.get("duration") or 0)
        thumbnail = (info.get("thumbnail") or
                     (info.get("thumbnails") or [{}])[-1].get("url", ""))
        uploader = info.get("uploader") or info.get("channel") or ""
        webpage_url = info.get("webpage_url") or info.get("original_url") or ""

        streams = self._collect_streams(info)
        media = MediaInfo(
            title=title,
            duration=duration,
            thumbnail_url=thumbnail,
            uploader=uploader,
            webpage_url=webpage_url,
            streams=streams,
            raw_info=info,
        )
        return media

    def _collect_streams(self, info: Dict[str, Any]) -> List[StreamFormat]:
        """Build the user-facing format list: video ladder + audio-only."""
        formats = info.get("formats") or []
        streams: List[StreamFormat] = []

        # Group progressive + video-only formats by height to deduplicate.
        best_by_height: Dict[int, Dict[str, Any]] = {}
        best_video_only: Dict[int, Dict[str, Any]] = {}
        best_audio: Optional[Dict[str, Any]] = None

        for f in formats:
            vcodec = (f.get("vcodec") or "none").lower()
            acodec = (f.get("acodec") or "none").lower()
            has_video = vcodec != "none"
            has_audio = acodec != "none"
            height = f.get("height") or 0

            if not has_video and has_audio:
                # Track the best-quality pure-audio stream.
                br = f.get("abr") or 0
                if best_audio is None or br > (best_audio.get("abr") or 0):
                    best_audio = f
                continue

            if not has_video:
                continue

            filesize = f.get("filesize") or f.get("filesize_approx") or 0
            if has_audio:
                # Progressive (video+audio in one file) - preferred if present.
                cur = best_by_height.get(height)
                if cur is None or filesize > (cur.get("filesize") or 0):
                    best_by_height[height] = f
            else:
                # Video-only - used when we need to merge with audio for HD.
                cur = best_video_only.get(height)
                if cur is None or filesize > (cur.get("filesize") or 0):
                    best_video_only[height] = f

        # Build the ladder from highest available resolution downward.
        available_heights = sorted(
            set(list(best_by_height.keys()) + list(best_video_only.keys())),
            reverse=True,
        )
        # If nothing matched the predefined ladder, use whatever exists.
        ordered_heights = ([h for h in self.QUALITY_LADDER if h in available_heights]
                           + [h for h in available_heights
                              if h not in self.QUALITY_LADDER])

        if not ordered_heights:
            # No discrete formats - offer yt-dlp's "best" selectors.
            streams.append(StreamFormat(
                label="Best Quality (auto)",
                format_id="best",
                needs_merge=False,
                ext=info.get("ext") or "mp4",
            ))
        else:
            for h in ordered_heights:
                prog = best_by_height.get(h)
                vonly = best_video_only.get(h)
                if prog:
                    streams.append(StreamFormat(
                        label=f"{self._h_label(h)} (MP4, no merge needed)",
                        format_id=prog["format_id"],
                        needs_merge=False,
                        ext=prog.get("ext") or "mp4",
                        filesize_approx=prog.get("filesize") or prog.get("filesize_approx"),
                    ))
                elif vonly:
                    needs_merge = self._any_audio_available(info)
                    streams.append(StreamFormat(
                        label=(f"{self._h_label(h)} (MP4"
                               + (", will merge audio" if needs_merge else ", video only")
                               + ")"),
                        format_id=vonly["format_id"],
                        needs_merge=needs_merge,
                        ext="mp4",
                        filesize_approx=vonly.get("filesize") or vonly.get("filesize_approx"),
                    ))

            # "Best" convenience option on top.
            streams.insert(0, StreamFormat(
                label="Best Quality (auto)",
                format_id="bestvideo*+bestaudio/best",
                needs_merge=True,
                ext="mp4",
            ))

        # Audio-only option.
        audio_ext = "m4a"
        audio_fmt = "bestaudio/best"
        if best_audio:
            audio_ext = best_audio.get("ext") or "m4a"
            audio_fmt = best_audio["format_id"]
        streams.append(StreamFormat(
            label=f"Audio Only ({audio_ext.upper()})",
            format_id=audio_fmt,
            is_audio_only=True,
            needs_merge=False,
            ext=audio_ext,
        ))
        return streams

    @staticmethod
    def _any_audio_available(info: Dict[str, Any]) -> bool:
        for f in info.get("formats") or []:
            acodec = (f.get("acodec") or "none").lower()
            vcodec = (f.get("vcodec") or "none").lower()
            if acodec != "none" and vcodec == "none":
                return True
        return False

    @staticmethod
    def _h_label(h: int) -> str:
        if h >= 2160:
            return f"{h}p (4K)"
        if h >= 1440:
            return f"{h}p (2K)"
        return f"{h}p"

    @staticmethod
    def _looks_like_url(text: str) -> bool:
        try:
            parsed = urlparse(text)
            return bool(parsed.scheme) and bool(parsed.netloc)
        except Exception:
            return False

    # ---- Download --------------------------------------------------------
    def download(
        self,
        url: str,
        stream: StreamFormat,
        destination: str,
        on_progress: Callable[[float, float, str, str], None],
        on_log: Callable[[str], None],
        on_done: Callable[[bool, str], None],
        cancel_event: threading.Event,
    ) -> None:
        """
        Download the selected stream. Runs in a worker thread.
        on_progress(percent, speed_mbps, eta_str, status_label)
        on_log(message)
        on_done(success, final_path_or_error)
        """
        try:
            if not destination or not os.path.isdir(destination):
                raise ValueError("Please choose a valid download folder.")

            os.makedirs(destination, exist_ok=True)

            base_opts: Dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "noplaylist": True,
                "ffmpeg_location": self._ffmpeg_path,
                "outtmpl": os.path.join(destination, "%(title).200B.%(ext)s"),
                "retries": 5,
                "fragment_retries": 5,
                "socket_timeout": 60,
                "concurrent_fragment_downloads": 4,
                "windowsfilenames": True,
                "restrictfilenames": False,
                "ignoreerrors": False,
            }

            if stream.is_audio_only:
                base_opts["format"] = stream.format_id
                base_opts["postprocessors"] = []
                base_opts["final_ext"] = stream.ext
                on_log("Extracting audio track...")
            elif stream.needs_merge:
                # Select video format + best audio, then merge to mp4/mkv.
                base_opts["format"] = f"{stream.format_id}+bestaudio[ext=m4a]/bestaudio/best"
                base_opts["merge_output_format"] = "mp4"
                base_opts["postprocessors"] = [{
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }]
                on_log("Downloading video and audio streams for merging...")
            else:
                base_opts["format"] = stream.format_id
                if stream.ext:
                    base_opts["final_ext"] = stream.ext

            def hook(d: Dict[str, Any]) -> None:
                if cancel_event.is_set():
                    raise yt_dlp.utils.DownloadCancelled("Cancelled by user.")

                status = d.get("status")
                if status == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes") or 0
                    speed = d.get("speed") or 0
                    eta = d.get("eta")
                    if total > 0:
                        percent = (downloaded / total) * 100
                    else:
                        # Fragments or unknown size: use fragment index.
                        frag = d.get("fragment_index") or 0
                        frag_count = d.get("fragment_count") or 0
                        percent = (frag / frag_count * 100) if frag_count else 0
                    speed_mbps = (speed / 1_000_000) if speed else 0.0
                    eta_str = self._format_eta(eta)
                    on_progress(percent, speed_mbps, eta_str, "Downloading")
                elif status == "postprocessing":
                    on_progress(100.0, 0.0, "", "Merging / Converting")
                    on_log("Post-processing: merging & encoding with FFmpeg...")
                elif status == "finished":
                    on_progress(100.0, 0.0, "", "Finalizing")
                    on_log("Download finished.")

            base_opts["progress_hooks"] = [hook]

            with yt_dlp.YoutubeDL(base_opts) as ydl:
                ydl.download([url])

            if cancel_event.is_set():
                on_done(False, "Download cancelled.")
                return

            final_path = self._find_final_file(destination, url, stream)
            on_done(True, final_path)

        except yt_dlp.utils.DownloadCancelled:
            on_done(False, "Download cancelled.")
        except yt_dlp.utils.ExtractorError as e:
            on_done(False, f"Extraction failed: {self._clean_error(str(e))}")
        except yt_dlp.utils.DownloadError as e:
            # yt-dlp wraps the real cause; unwrap for a friendlier message.
            cause = e.cause if getattr(e, "cause", None) else e
            msg = str(cause)
            if "ffmpeg" in msg.lower() or "ffprobe" in msg.lower():
                msg = ("FFmpeg could not be found or failed. "
                       "Install FFmpeg and ensure it is on your PATH, "
                       "then try again. (Details: " + msg + ")")
            on_done(False, f"Download failed: {self._clean_error(msg)}")
        except Exception as e:  # noqa: BLE001 - last-resort safety net
            on_done(False, f"Unexpected error: {self._clean_error(str(e))}")
        finally:
            try:
                on_progress(0.0, 0.0, "", "Idle")
            except Exception:
                pass

    @staticmethod
    def _find_final_file(destination: str, url: str,
                         stream: StreamFormat) -> str:
        """Best-effort: return the most recently created media file."""
        candidates: List[str] = []
        for root, _dirs, files in os.walk(destination):
            for name in files:
                full = os.path.join(root, name)
                candidates.append(full)
        if not candidates:
            return destination
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]

    @staticmethod
    def _format_eta(eta: Optional[int]) -> str:
        if eta is None or eta < 0:
            return "--:--"
        m, s = divmod(int(eta), 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    @staticmethod
    def _clean_error(msg: str) -> str:
        """Strip noise from yt-dlp/ffmpeg error strings for the UI."""
        msg = re.sub(r"^(ERROR|WARNING):\s*", "", msg, flags=re.IGNORECASE)
        if len(msg) > 400:
            msg = msg[:400] + "..."
        return msg.strip()


# =====================================================================
# DOWNLOAD HISTORY (Supabase-backed)
# =====================================================================
@dataclass
class HistoryRecord:
    """A single completed/failed download persisted to Supabase."""
    id: str = ""
    title: str = ""
    url: str = ""
    quality: str = ""
    file_path: str = ""
    status: str = "completed"
    file_size: Optional[int] = None
    error_msg: str = ""
    created_at: str = ""


def _load_supabase_env() -> Dict[str, str]:
    """Read Supabase URL + anon key from .env (VITE_-prefixed or plain)."""
    env: Dict[str, str] = {}
    candidates = [os.path.join(os.getcwd(), ".env"),
                  os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")]
    seen = set()
    for path in candidates:
        if path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    env[key.strip()] = value.strip().strip('"').strip("'")
        except OSError:
            continue
    # Accept either VITE_ or non-VITE prefixes.
    out = {
        "url": env.get("VITE_SUPABASE_URL") or env.get("SUPABASE_URL") or "",
        "anon_key": (env.get("VITE_SUPABASE_ANON_KEY")
                     or env.get("SUPABASE_ANON_KEY") or ""),
    }
    return out


class HistoryStore:
    """
    Persists download history to the Supabase `download_history` table via
    the PostgREST API (no extra dependency - uses urllib).

    Every method is safe to call from a worker thread and degrades silently
    if Supabase is unreachable: the app keeps working offline and history
    simply isn't recorded/loaded.
    """

    TABLE = "download_history"

    def __init__(self) -> None:
        env = _load_supabase_env()
        self._url = env["url"].rstrip("/")
        self._key = env["anon_key"]
        self._enabled = bool(self._url and self._key)
        self._timeout = 20

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str,
                 body: Optional[Dict[str, Any]] = None) -> Any:
        import json
        import urllib.request
        import urllib.error
        full = f"{self._url}/rest/v1/{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(full, data=data, method=method,
                                     headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Supabase HTTP {e.code}: "
                               f"{e.read().decode('utf-8', 'replace')[:200]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Supabase unreachable: {e.reason}")
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Supabase request failed: {e}")

    def add(self, rec: HistoryRecord) -> None:
        """Insert a history record. Silently no-ops if disabled."""
        if not self._enabled:
            return
        payload = {
            "title": rec.title[:500],
            "url": rec.url[:2000],
            "quality": rec.quality[:200],
            "file_path": rec.file_path[:1000],
            "status": rec.status,
            "file_size": rec.file_size,
            "error_msg": (rec.error_msg or "")[:1000],
        }
        try:
            self._request("POST", self.TABLE, payload)
        except Exception as e:  # noqa: BLE001 - history is best-effort
            # Don't let a logging failure break the download flow.
            print(f"[Flash Media] history insert failed: {e}", flush=True)

    def list(self, limit: int = 100) -> List[HistoryRecord]:
        """Return recent history, newest first. Empty list if disabled/error."""
        if not self._enabled:
            return []
        path = (f"{self.TABLE}?order=created_at.desc&limit={limit}"
                f"&select=id,title,url,quality,file_path,status,file_size,"
                f"error_msg,created_at")
        try:
            rows = self._request("GET", path) or []
            return [HistoryRecord(
                id=str(r.get("id", "")),
                title=r.get("title", ""),
                url=r.get("url", ""),
                quality=r.get("quality", ""),
                file_path=r.get("file_path", ""),
                status=r.get("status", ""),
                file_size=r.get("file_size"),
                error_msg=r.get("error_msg", "") or "",
                created_at=r.get("created_at", ""),
            ) for r in rows]
        except Exception as e:  # noqa: BLE001
            print(f"[Flash Media] history load failed: {e}", flush=True)
            return []

    def clear(self) -> bool:
        """Delete all history rows. Returns True on success."""
        if not self._enabled:
            return False
        try:
            self._request("DELETE", f"{self.TABLE}?id=neq.00000000-0000-0000-"
                                    "0000-000000000000")
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[Flash Media] history clear failed: {e}", flush=True)
            return False


# =====================================================================
# UI HELPERS
# =====================================================================
def fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return "--:--"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_size(num_bytes: Optional[int]) -> str:
    if not num_bytes or num_bytes <= 0:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


# =====================================================================
# UI COMPONENTS
# =====================================================================
class PreviewPanel(ctk.CTkFrame):
    """Shows thumbnail, title, duration, uploader once a link is parsed."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs: Any) -> None:
        super().__init__(master, fg_color=THEME["bg_elevated"],
                         corner_radius=14, **kwargs)
        self._thumb_image: Optional[ImageTk.PhotoImage] = None
        self.grid_columnconfigure(1, weight=1)

        self._thumb_box = ctk.CTkLabel(self, text="", fg_color=THEME["surface"],
                                       corner_radius=10, width=180, height=101,
                                       anchor="center")
        self._thumb_box.grid(row=0, column=0, padx=(14, 12), pady=(14, 14),
                             sticky="ns")
        self._thumb_box.configure(text="No media")

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, padx=(0, 14), pady=14, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        self._title_label = ctk.CTkLabel(
            right, text="Paste a link and click Analyze to see media details.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color=THEME["text"], wraplength=420, anchor="w",
            justify="left")
        self._title_label.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self._meta_label = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_muted"], anchor="w", justify="left")
        self._meta_label.grid(row=1, column=0, sticky="ew")

    def show_info(self, info: MediaInfo, thumb_image: Optional[Image.Image]) -> None:
        self._title_label.configure(text=info.title or "Untitled")
        meta_parts = []
        if info.duration:
            meta_parts.append(f"Duration  {fmt_duration(info.duration)}")
        if info.uploader:
            meta_parts.append(f"By  {info.uploader}")
        self._meta_label.configure(text="    ".join(meta_parts))

        if thumb_image:
            try:
                thumb = thumb_image.copy()
                thumb.thumbnail((180, 101))
                self._thumb_image = ImageTk.PhotoImage(thumb)
                self._thumb_box.configure(image=self._thumb_image, text="")
            except Exception:
                self._thumb_box.configure(image=None, text="No preview")
        else:
            self._thumb_box.configure(image=None, text="No preview")

    def reset(self) -> None:
        self._title_label.configure(
            text="Paste a link and click Analyze to see media details.")
        self._meta_label.configure(text="")
        self._thumb_box.configure(image=None, text="No media")
        self._thumb_image = None


class QualitySelector(ctk.CTkFrame):
    """Quality/Format selection with a descriptive label header."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs: Any) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Quality / Format",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                     text_color=THEME["text"]).grid(row=0, column=0, padx=(4, 12),
                                                    sticky="w")
        self._menu = ctk.CTkOptionMenu(
            self, fg_color=THEME["surface"],
            button_color=THEME["secondary"],
            button_hover_color=THEME["secondary_hover"],
            text_color=THEME["text"],
            dropdown_fg_color=THEME["bg_elevated"],
            dropdown_hover_color=THEME["secondary"],
            dropdown_text_color=THEME["text"],
            values=["-- Analyze a link first --"],
            height=36, corner_radius=8,
        )
        self._menu.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self._menu.configure(state="disabled")
        self._streams: List[StreamFormat] = []

    def populate(self, streams: List[StreamFormat]) -> None:
        self._streams = streams
        if not streams:
            self._menu.configure(values=["-- No formats available --"],
                                 state="disabled")
            return
        labels = [self._label_with_size(s) for s in streams]
        self._menu.configure(values=labels, state="normal")
        self._menu.set(labels[0])

    def selected(self) -> Optional[StreamFormat]:
        if not self._streams:
            return None
        current = self._menu.get()
        for s in self._streams:
            if self._label_with_size(s) == current:
                return s
        return self._streams[0]

    def lock(self) -> None:
        self._menu.configure(state="disabled")

    def unlock(self) -> None:
        if self._streams:
            self._menu.configure(state="normal")

    @staticmethod
    def _label_with_size(s: StreamFormat) -> str:
        if s.filesize_approx:
            return f"{s.label}  -  {fmt_size(s.filesize_approx)}"
        return s.label


class ProgressBlock(ctk.CTkFrame):
    """Progress bar + percentage + speed + status."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs: Any) -> None:
        super().__init__(master, fg_color=THEME["bg_elevated"],
                         corner_radius=14, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        self._status = ctk.CTkLabel(
            top, text="Idle",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_muted"], anchor="w")
        self._status.grid(row=0, column=0, sticky="w")

        self._percent = ctk.CTkLabel(
            top, text="0%",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=THEME["accent"], anchor="e")
        self._percent.grid(row=0, column=1, sticky="e")

        self._bar = ctk.CTkProgressBar(self, height=14, corner_radius=7,
                                       progress_color=THEME["accent"],
                                       fg_color=THEME["surface"])
        self._bar.grid(row=1, column=0, padx=16, pady=(2, 10), sticky="ew")
        self._bar.set(0)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="ew")
        bottom.grid_columnconfigure(1, weight=1)
        self._speed = ctk.CTkLabel(
            bottom, text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_muted"], anchor="w")
        self._speed.grid(row=0, column=0, sticky="w")
        self._eta = ctk.CTkLabel(
            bottom, text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_muted"], anchor="e")
        self._eta.grid(row=0, column=1, sticky="e")

    def update(self, percent: float, speed: float, eta: str, status: str) -> None:
        self._bar.set(max(0.0, min(1.0, percent / 100.0)))
        self._percent.configure(text=f"{percent:0.1f}%")
        self._status.configure(text=status or "Idle")
        self._speed.configure(text=f"{speed:0.2f} MB/s" if speed > 0 else "")
        self._eta.configure(text=f"ETA {eta}" if eta and eta != "--:--" else "")

    def set_status(self, text: str, color: str = THEME["text_muted"]) -> None:
        self._status.configure(text=text, text_color=color)

    def reset(self) -> None:
        self._bar.set(0)
        self._percent.configure(text="0%")
        self._status.configure(text="Idle", text_color=THEME["text_muted"])
        self._speed.configure(text="")
        self._eta.configure(text="")


class HistoryPanel(ctk.CTkScrollableFrame):
    """Scrollable list of past downloads with re-open + clear actions."""

    def __init__(self, master: ctk.CTkBaseClass,
                 on_clear: Callable[[], None], **kwargs: Any) -> None:
        super().__init__(master, fg_color=THEME["bg_elevated"],
                         corner_radius=14, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._on_clear = on_clear
        self._rows: List[ctk.CTkFrame] = []

    def populate(self, records: List[HistoryRecord]) -> None:
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        if not records:
            empty = ctk.CTkLabel(
                self, text="No downloads yet.\nYour completed and failed "
                           "downloads will appear here.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                text_color=THEME["text_muted"], justify="center")
            empty.grid(row=0, column=0, pady=40, padx=20)
            self._rows.append(empty)
            return

        for idx, rec in enumerate(records):
            row = self._make_row(rec, idx)
            row.grid(row=idx, column=0, padx=10, pady=6, sticky="ew")
            self._rows.append(row)

    def _make_row(self, rec: HistoryRecord, idx: int) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self, fg_color=THEME["surface"], corner_radius=10)
        row.grid_columnconfigure(0, weight=1)

        title_text = rec.title or rec.url or "Untitled"
        status_color = (THEME["success"] if rec.status == "completed"
                        else THEME["error"])
        status_dot = "\u25CF"  # filled circle

        head = ctk.CTkFrame(row, fg_color="transparent")
        head.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head, text=title_text[:80],
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=THEME["text"], anchor="w").grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(
            head, text=f"{status_dot} {rec.status}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=status_color, anchor="e").grid(
            row=0, column=1, padx=(8, 0), sticky="e")

        meta_parts = []
        if rec.quality:
            meta_parts.append(rec.quality)
        if rec.file_size:
            meta_parts.append(fmt_size(rec.file_size))
        if rec.created_at:
            meta_parts.append(rec.created_at[:16].replace("T", " "))
        meta = "   |   ".join(meta_parts) if meta_parts else "-"
        ctk.CTkLabel(
            row, text=meta,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=THEME["text_muted"], anchor="w").grid(
            row=1, column=0, padx=12, sticky="w")

        if rec.status == "failed" and rec.error_msg:
            ctk.CTkLabel(
                row, text=rec.error_msg[:120],
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=THEME["error"], anchor="w", wraplength=560).grid(
                row=2, column=0, padx=12, pady=(2, 8), sticky="w")
        elif rec.file_path:
            ctk.CTkLabel(
                row, text=rec.file_path,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=THEME["text_muted"], anchor="w", wraplength=560).grid(
                row=2, column=0, padx=12, pady=(2, 8), sticky="w")
        return row


# =====================================================================
# MAIN APPLICATION
# =====================================================================
class FlashMediaApp(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Flash Media  -  Universal Downloader")
        self.geometry("720x820")
        self.minsize(620, 760)
        self.configure(fg_color=THEME["bg"])

        self._engine = DownloadEngine()
        self._history = HistoryStore()
        self._media: Optional[MediaInfo] = None
        self._cancel_event = threading.Event()
        self._busy = False
        self._worker: Optional[threading.Thread] = None
        self._last_stream: Optional[StreamFormat] = None
        self._last_url: str = ""

        self._build_ui()
        self.after(200, self._warn_if_no_ffmpeg)
        self.after(400, self._load_history_async)

    # ---- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color=THEME["bg_elevated"],
                              corner_radius=14)
        header.grid(row=0, column=0, padx=20, pady=(20, 12), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="\u26A1 FLASH MEDIA",
            font=ctk.CTkFont(family=FONT_FAMILY, size=24, weight="bold"),
            text_color=THEME["accent"]).grid(row=0, column=0, pady=14)
        ctk.CTkLabel(
            header, text="Download video & audio from thousands of sites",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_muted"]).grid(row=1, column=0, pady=(0, 12))

        # Tabbed view: Download + History
        self._tabs = ctk.CTkTabview(
            self, fg_color=THEME["bg"],
            segmented_button_fg_color=THEME["bg_elevated"],
            segmented_button_selected_color=THEME["accent"],
            segmented_button_selected_hover_color=THEME["accent_hover"],
            segmented_button_unselected_color=THEME["secondary"],
            segmented_button_unselected_hover_color=THEME["secondary_hover"],
            text_color=THEME["text"])
        self._tabs.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="nsew")
        self.grid_rowconfigure(1, weight=1)
        self._tab_download = self._tabs.add("Download")
        self._tab_history = self._tabs.add("History")
        self._tab_download.grid_columnconfigure(0, weight=1)
        self._tab_download.grid_rowconfigure(4, weight=0)
        self._tab_history.grid_columnconfigure(0, weight=1)
        self._tab_history.grid_rowconfigure(0, weight=1)

        self._build_download_tab(self._tab_download)
        self._build_history_tab(self._tab_history)

        # Status / log line at the very bottom
        self._log_label = ctk.CTkLabel(
            self, text="Ready.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_muted"], anchor="w")
        self._log_label.grid(row=2, column=0, padx=24, pady=(0, 14), sticky="ew")

    def _build_download_tab(self, parent: ctk.CTkFrame) -> None:
        # URL input block
        url_block = ctk.CTkFrame(parent, fg_color=THEME["bg_elevated"],
                                 corner_radius=14)
        url_block.grid(row=0, column=0, padx=0, pady=(0, 12), sticky="ew")
        url_block.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            url_block, text="Media Link",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=THEME["text"]).grid(row=0, column=0, padx=16,
                                           pady=(14, 4), sticky="w")
        self._url_entry = ctk.CTkEntry(
            url_block, placeholder_text="Paste a YouTube / Vimeo / Twitter / "
            "any supported media URL here...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            fg_color=THEME["surface"], text_color=THEME["text"],
            border_color=THEME["border"], border_width=1,
            height=42, corner_radius=10)
        self._url_entry.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")
        self._url_entry.bind("<Return>", lambda _e: self.on_analyze())

        self._analyze_btn = ctk.CTkButton(
            url_block, text="Analyze Link", command=self.on_analyze,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=THEME["accent"], hover_color=THEME["accent_hover"],
            text_color="#0B1B1C", height=42, corner_radius=10)
        self._analyze_btn.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="ew")

        # Preview + quality
        preview_block = ctk.CTkFrame(parent, fg_color="transparent")
        preview_block.grid(row=1, column=0, pady=(0, 12), sticky="ew")
        preview_block.grid_columnconfigure(0, weight=1)

        self._preview = PreviewPanel(preview_block)
        self._preview.grid(row=0, column=0, pady=(0, 12), sticky="ew")

        self._quality = QualitySelector(preview_block)
        self._quality.grid(row=1, column=0, pady=(0, 4), sticky="ew")

        # Progress
        self._progress = ProgressBlock(parent)
        self._progress.grid(row=2, column=0, pady=12, sticky="ew")

        # Destination + actions
        action_block = ctk.CTkFrame(parent, fg_color=THEME["bg_elevated"],
                                    corner_radius=14)
        action_block.grid(row=3, column=0, pady=(12, 20), sticky="ew")
        action_block.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(action_block, text="Save To",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=13,
                                      weight="bold"),
                     text_color=THEME["text"]).grid(row=0, column=0, padx=16,
                                                    pady=(14, 4), sticky="w")
        dest_row = ctk.CTkFrame(action_block, fg_color="transparent")
        dest_row.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")
        dest_row.grid_columnconfigure(0, weight=1)
        self._dest_var = ctk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self._dest_entry = ctk.CTkEntry(
            dest_row, textvariable=self._dest_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=THEME["surface"], text_color=THEME["text"],
            border_color=THEME["border"], border_width=1,
            height=38, corner_radius=9)
        self._dest_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._dest_btn = ctk.CTkButton(
            dest_row, text="Browse", width=100, command=self.on_browse,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=THEME["secondary"], hover_color=THEME["secondary_hover"],
            text_color=THEME["text"], height=38, corner_radius=9)
        self._dest_btn.grid(row=0, column=1)

        btn_row = ctk.CTkFrame(action_block, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        self._download_btn = ctk.CTkButton(
            btn_row, text="Start Download", command=self.on_download,
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            fg_color=THEME["accent"], hover_color=THEME["accent_hover"],
            text_color="#0B1B1C", height=46, corner_radius=11,
            state="disabled")
        self._download_btn.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self._cancel_btn = ctk.CTkButton(
            btn_row, text="Cancel", width=120, command=self.on_cancel,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=THEME["error"], hover_color="#FF7575",
            text_color="#FFFFFF", height=46, corner_radius=11,
            state="disabled")
        self._cancel_btn.grid(row=0, column=1)

    def _build_history_tab(self, parent: ctk.CTkFrame) -> None:
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=1, column=0, pady=(0, 10), sticky="ew")
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            toolbar, text="Recent Downloads",
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color=THEME["text"], anchor="w").grid(
            row=0, column=0, sticky="w")
        self._refresh_btn = ctk.CTkButton(
            toolbar, text="Refresh", width=90, command=self._load_history_async,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["secondary"], hover_color=THEME["secondary_hover"],
            text_color=THEME["text"], height=32, corner_radius=8)
        self._refresh_btn.grid(row=0, column=1, padx=(8, 0))
        self._clear_btn = ctk.CTkButton(
            toolbar, text="Clear All", width=90, command=self._on_clear_history,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["error"], hover_color="#FF7575",
            text_color="#FFFFFF", height=32, corner_radius=8)
        self._clear_btn.grid(row=0, column=2, padx=(8, 0))

        self._history_panel = HistoryPanel(
            parent, on_clear=self._load_history_async)
        self._history_panel.grid(row=0, column=0, sticky="nsew")

    # ---- Thread-safe UI helpers -----------------------------------------
    def _safe(self, fn: Callable[[], None]) -> None:
        """Run a UI mutation on the main thread (Tk isn't thread-safe)."""
        self.after(0, fn)

    def _log(self, message: str, color: str = THEME["text_muted"]) -> None:
        def _do() -> None:
            self._log_label.configure(text=message, text_color=color)
        self._safe(_do)

    def _set_busy(self, busy: bool, mode: str = "analyze") -> None:
        def _do() -> None:
            self._busy = busy
            if mode == "analyze":
                self._analyze_btn.configure(
                    state="disabled" if busy else "normal",
                    text="Analyzing..." if busy else "Analyze Link")
                self._download_btn.configure(state="disabled")
            else:  # download
                self._analyze_btn.configure(state="disabled" if busy else "normal")
                self._download_btn.configure(
                    state="disabled" if busy else
                    ("normal" if self._media else "disabled"),
                    text="Downloading..." if busy else "Start Download")
                self._cancel_btn.configure(
                    state="normal" if busy else "disabled")
                self._quality.lock() if busy else self._quality.unlock()
        self._safe(_do)

    # ---- Actions ---------------------------------------------------------
    def on_analyze(self) -> None:
        if self._busy:
            return
        url = (self._url_entry.get() or "").strip()
        if not url:
            self._log("Please paste a media link first.", THEME["warning"])
            return
        self._set_busy(True, "analyze")
        self._preview.reset()
        self._quality.populate([])
        self._download_btn.configure(state="disabled")
        self._progress.reset()
        self._log("Analyzing link...", THEME["text_muted"])
        self._media = None

        def worker() -> None:
            try:
                media = self._engine.extract(url, on_log=lambda m: self._log(m))
                thumb = self._fetch_thumbnail(media.thumbnail_url)
                self._safe(lambda: self._apply_media(media, thumb))
            except ValueError as e:
                self._safe(lambda: self._on_analyze_fail(str(e),
                                                          THEME["warning"]))
            except yt_dlp.utils.ExtractorError as e:
                self._safe(lambda: self._on_analyze_fail(
                    f"Couldn't extract: {DownloadEngine._clean_error(str(e))}",
                    THEME["error"]))
            except Exception as e:  # noqa: BLE001
                self._safe(lambda: self._on_analyze_fail(
                    f"Analysis failed: {DownloadEngine._clean_error(str(e))}",
                    THEME["error"]))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _apply_media(self, media: MediaInfo, thumb: Optional[Image.Image]) -> None:
        self._media = media
        self._preview.show_info(media, thumb)
        self._quality.populate(media.streams)
        self._download_btn.configure(state="normal")
        self._set_busy(False, "analyze")
        count = len(media.streams)
        self._log(f"Found {count} format{'s' if count != 1 else ''}. "
                  f"Pick a quality and press Start Download.", THEME["success"])
        self._progress.set_status("Ready to download", THEME["success"])

    def _on_analyze_fail(self, message: str, color: str) -> None:
        self._set_busy(False, "analyze")
        self._log(message, color)
        self._progress.set_status("Analysis failed", THEME["error"])
        self._media = None

    def _fetch_thumbnail(self, url: str) -> Optional[Image.Image]:
        if not url:
            return None
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "FlashMedia/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            return Image.open(io.BytesIO(data))
        except Exception:
            return None

    def on_browse(self) -> None:
        if self._busy:
            return
        chosen = ctk.filedialog.askdirectory(
            initialdir=self._dest_var.get() or os.path.expanduser("~"),
            title="Choose download folder")
        if chosen:
            self._dest_var.set(chosen)

    def on_download(self) -> None:
        if self._busy:
            return
        if not self._media:
            self._log("Analyze a link first.", THEME["warning"])
            return
        stream = self._quality.selected()
        if not stream:
            self._log("Please select a quality/format.", THEME["warning"])
            return
        destination = self._dest_var.get().strip()
        if not destination or not os.path.isdir(destination):
            self._log("Choose a valid save folder (Browse).", THEME["warning"])
            return

        self._cancel_event.clear()
        self._set_busy(True, "download")
        self._progress.reset()
        self._log("Starting download...", THEME["text_muted"])

        url = self._media.webpage_url or (self._url_entry.get() or "").strip()
        self._last_url = url
        self._last_stream = stream
        on_progress = self._on_progress
        on_log = self._log
        on_done = self._on_done
        cancel = self._cancel_event

        def worker() -> None:
            self._engine.download(url, stream, destination,
                                  on_progress, on_log, on_done, cancel)

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def on_cancel(self) -> None:
        if not self._busy:
            return
        self._cancel_event.set()
        self._log("Cancelling...", THEME["warning"])

    # ---- Download callbacks (called from worker thread) ------------------
    def _on_progress(self, percent: float, speed: float,
                     eta: str, status: str) -> None:
        def _do() -> None:
            self._progress.update(percent, speed, eta, status)
        self._safe(_do)

    def _on_done(self, success: bool, message: str) -> None:
        # Determine file size of the saved file (best-effort).
        file_size: Optional[int] = None
        if success and message and os.path.isfile(message):
            try:
                file_size = os.path.getsize(message)
            except OSError:
                file_size = None

        title = self._media.title if self._media else ""
        quality = self._last_stream.label if self._last_stream else ""

        def _do() -> None:
            self._set_busy(False, "download")
            if success:
                self._progress.set_status("Complete", THEME["success"])
                self._progress._bar.set(1.0)
                self._progress._percent.configure(text="100%")
                self._log(f"Saved to: {message}", THEME["success"])
            else:
                self._progress.set_status("Cancelled / Failed", THEME["error"])
                self._log(message, THEME["error"])

            # Persist to download history (off the UI thread, best-effort).
            rec = HistoryRecord(
                title=title,
                url=self._last_url,
                quality=quality,
                file_path=message if success else "",
                status="completed" if success else "failed",
                file_size=file_size,
                error_msg="" if success else message,
            )
            threading.Thread(
                target=self._history.add, args=(rec,), daemon=True).start()

        self._safe(_do)

    # ---- History ---------------------------------------------------------
    def _load_history_async(self) -> None:
        """Fetch history in a worker thread, then render on the UI thread."""
        def worker() -> None:
            records = self._history.list(limit=100)
            self._safe(lambda: self._history_panel.populate(records))
            if not self._history.enabled:
                self._safe(lambda: self._log(
                    "History sync off (no Supabase config).",
                    THEME["text_muted"]))
        threading.Thread(target=worker, daemon=True).start()

    def _on_clear_history(self) -> None:
        if not self._history.enabled:
            self._log("History sync is off - nothing to clear.",
                      THEME["text_muted"])
            return
        self._log("Clearing history...", THEME["text_muted"])

        def worker() -> None:
            ok = self._history.clear()
            def _done() -> None:
                if ok:
                    self._history_panel.populate([])
                    self._log("History cleared.", THEME["success"])
                else:
                    self._log("Could not clear history.", THEME["error"])
            self._safe(_done)

        threading.Thread(target=worker, daemon=True).start()

    # ---- Housekeeping ----------------------------------------------------
    def _warn_if_no_ffmpeg(self) -> None:
        if not self._engine.ffmpeg_available:
            self._log("Warning: FFmpeg not found. HD merges will fail. "
                      "Install FFmpeg and add it to PATH.", THEME["warning"])

    def report_callback_exception(self, exc: Exception, val: Any,
                                  tb: Any) -> None:  # pragma: no cover
        # Keep the app alive even if an unexpected Tk exception fires.
        detail = "".join(traceback.format_exception(exc, val, tb))
        try:
            self._log(f"UI error: {val}", THEME["error"])
        except Exception:
            pass
        traceback.print_exception(exc, val, tb)


# =====================================================================
# ENTRY POINT
# =====================================================================
def main() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")  # overridden by our explicit palette
    app = FlashMediaApp()
    app.mainloop()


if __name__ == "__main__":
    main()


# =====================================================================
# QUICK START (README)
# =====================================================================
# Flash Media - Universal Media Downloader
# ----------------------------------------
# A dark-mode desktop app for downloading video/audio from thousands of
# sites (YouTube, Vimeo, Twitter, Twitch, and more) using yt-dlp, with
# automatic HD video+audio merging via FFmpeg, and a Supabase-backed
# download history.
#
# REQUIREMENTS
#   - Python 3.9+
#   - FFmpeg installed and on your system PATH
#       macOS:    brew install ffmpeg
#       Ubuntu:   sudo apt install ffmpeg
#       Windows:  download from ffmpeg.org, add bin/ to PATH
#   - Python packages:
#       pip install customtkinter yt-dlp Pillow
#   - Supabase: a .env file in the app folder with
#       VITE_SUPABASE_URL=...   and   VITE_SUPABASE_ANON_KEY=...
#     (The download_history table is created automatically on first run
#      via the bundled migration; history degrades gracefully to offline
#      if Supabase is unreachable - the app still works.)
#
# RUN
#   python flash_media.py
#
# HOW IT WORKS
#   1. Paste a media URL and click "Analyze Link".
#   2. The app extracts title, duration, thumbnail, and available formats
#      in a background thread (UI never freezes).
#   3. Pick a quality from the dropdown (or "Audio Only").
#   4. Choose a save folder with "Browse".
#   5. Click "Start Download". Progress, speed, and ETA update live.
#      HD streams that ship video and audio separately are merged
#      automatically into a single .mp4 via FFmpeg.
#   6. Click "Cancel" any time to stop safely.
#   7. Every completed or failed download is saved to the History tab
#      (backed by Supabase), with title, quality, size, status, and path.
#      Use Refresh to reload and Clear All to wipe the history.
#
# NOTES
#   - Keep yt-dlp updated:  pip install -U yt-dlp   (sites change often)
#   - The app processes single videos; for a playlist it uses the first
#     entry to keep the UI simple.
# =====================================================================
