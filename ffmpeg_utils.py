"""
Bringas Cut — ffmpeg_utils.py
Core logic (no GUI) for Bringas Cut.

Locked spec (2026-11-08, user discussion):
- Windows app, Python Tkinter stdlib-only + ffmpeg.
- Input: ONE local video file (no YouTube download).
- Chop it into many clips. Audio from the original is REMOVED
  totally (-an) on every clip.
- Clip duration CUSTOM: user sets Min and Max seconds
  (default Min 3, Max 8). Each clip duration is random uniform
  in [Min, Max].
- Remainder rule (user did not answer; this is the documented
  decision): if the tail remainder is < Min, merge it into the
  last clip (extend the last clip) — never emit a tiny <Min clip,
  except when the whole video itself is shorter than Min
  (then one clip = whole video).
- Effect intensity: 3 options — "Lembut banget", "Lembut"
  (default), "Guncang". Scales zoom/shake amplitude.
- Effects: each clip gets ONE random effect, DIFFERENT from
  other clips — shuffled 8-effect pool, cycled: use all 8 before
  repeating, reshuffle each cycle, no two adjacent clips share
  the same effect (cycle boundary fixed by swapping).
  Pool: zoom_in, zoom_out, zoom_breathe, pan_left, pan_right,
  pan_up, shake_soft, zoom_shake. No mirror/flip.
- Output filenames RANDOM, not sequential: random 10-char
  [a-z0-9] + .mp4, regenerated on collision. No klip_01/klip_02.
- Quality HIGH: keep original width/height/fps, re-encode per
  clip. CPU libx264 CRF 18 preset veryfast; GPU if detected:
  NVENC p4+CQ19 / QSV medium+ICQ19 / AMF balanced+CQP19.
- No output verification ("sikat aja"): ffmpeg exit 0 + file
  exists = success.
- No black cmd window on Windows: CREATE_NO_WINDOW for all
  ffmpeg/ffprobe subprocesses.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import string
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts"}

LogFn = Callable[[str], None]


def _noop_log(msg: str) -> None:
    pass


# --------------------------------------------------------------------------
# ffmpeg / ffprobe discovery
# --------------------------------------------------------------------------

def find_ffmpeg(explicit: Optional[str] = None) -> str:
    """Return ffmpeg executable path. App folder first, then PATH."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    here = Path(__file__).resolve().parent
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidates.append(str(here / name))
    candidates.append("ffmpeg")
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
        if os.path.isfile(c):
            return c
    return "ffmpeg"


def find_ffprobe(explicit: Optional[str] = None) -> str:
    candidates = []
    if explicit:
        candidates.append(explicit)
    here = Path(__file__).resolve().parent
    for name in ("ffprobe.exe", "ffprobe"):
        candidates.append(str(here / name))
    candidates.append("ffprobe")
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
        if os.path.isfile(c):
            return c
    return "ffprobe"


def _no_window_kwargs() -> dict:
    """Windows: hide the console window for ffmpeg/ffprobe children."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def _run(cmd: List[str], log: LogFn = _noop_log) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **_no_window_kwargs())


# --------------------------------------------------------------------------
# Probing
# --------------------------------------------------------------------------

@dataclass
class MediaInfo:
    path: str
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""


def _to_float(v) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _fps(fr) -> float:
    try:
        num, den = str(fr).split("/")
        return float(num) / float(den) if float(den) else 0.0
    except Exception:
        return 0.0


def _duration_from_probe(data: dict) -> float:
    """Best-effort duration from one ffprobe JSON dump.

    Fallback chain (same as Bringas Render PC):
    1. format duration
    2. any stream duration (video first, then the rest)
    3. video frames / fps
    """
    dur = _to_float((data.get("format") or {}).get("duration"))
    if dur > 0:
        return dur
    streams = data.get("streams") or []
    for s in streams:
        if s.get("codec_type") == "video":
            d = _to_float(s.get("duration"))
            if d > 0:
                return d
    for s in streams:
        d = _to_float(s.get("duration"))
        if d > 0:
            return d
    for s in streams:
        if s.get("codec_type") == "video":
            frames = _to_float(s.get("nb_frames"))
            fps = _fps(s.get("avg_frame_rate") or s.get("r_frame_rate"))
            if frames > 0 and fps > 0:
                return frames / fps
    return 0.0


def probe_duration(path: str, ffprobe: Optional[str] = None) -> float:
    """Duration in seconds via ffprobe, 0.0 on failure."""
    fp = find_ffprobe(ffprobe)
    cmd = [fp, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           **_no_window_kwargs())
        data = json.loads(r.stdout or "{}")
        return _duration_from_probe(data)
    except Exception:
        return 0.0


def probe_specs(path: str, ffprobe: Optional[str] = None) -> MediaInfo:
    """Width/height/fps/codec + duration via ffprobe."""
    info = MediaInfo(path=path)
    fp = find_ffprobe(ffprobe)
    cmd = [fp, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           **_no_window_kwargs())
        data = json.loads(r.stdout or "{}")
        info.duration = _duration_from_probe(data)
        for s in data.get("streams", []):
            if s.get("codec_type") == "video" and not info.codec:
                info.codec = s.get("codec_name", "")
                info.width = int(s.get("width", 0) or 0)
                info.height = int(s.get("height", 0) or 0)
                fr = s.get("r_frame_rate") or s.get("avg_frame_rate") or "0/1"
                info.fps = _fps(fr)
    except Exception:
        pass
    return info


# --------------------------------------------------------------------------
# GPU detection (NVENC / Quick Sync / AMF) — same pattern as Bringas
# --------------------------------------------------------------------------

_GPU_ENCODERS = ("h264_nvenc", "h264_qsv", "h264_amf")
_GPU_CACHE: dict = {}


def parse_encoders_list(text: str) -> List[str]:
    """Hardware H.264 encoders in `ffmpeg -encoders` output, in
    priority order (NVENC > QSV > AMF). Pure function, easy to test."""
    found = set()
    for line in (text or "").splitlines():
        for tok in line.split():
            if tok in _GPU_ENCODERS:
                found.add(tok)
    return [name for name in _GPU_ENCODERS if name in found]


def parse_encoders_output(text: str) -> Optional[str]:
    """Best hardware H.264 encoder found in `ffmpeg -encoders` output,
    or None."""
    lst = parse_encoders_list(text)
    return lst[0] if lst else None


def _encoder_probe_ok(ffmpeg: str, encoder: str) -> bool:
    """True if `encoder` actually works on this machine.

    `ffmpeg -encoders` only lists compiled-in encoders — NVENC is
    listed even without an NVIDIA GPU, so a tiny 1-frame encode is
    the real test (fails fast without the driver/hardware).
    """
    try:
        r = subprocess.run(
            [ffmpeg, "-hide_banner", "-y",
             "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
             "-frames:v", "1", "-c:v", encoder, "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
            **_no_window_kwargs())
        return r.returncode == 0
    except Exception:
        return False


def detect_gpu_encoder(ffmpeg: Optional[str] = None) -> Optional[str]:
    """Detect the best hardware H.264 encoder this ffmpeg supports
    AND that actually works on this machine. Cached per ffmpeg path.
    Never raises — any failure means CPU fallback."""
    ff = find_ffmpeg(ffmpeg)
    if ff in _GPU_CACHE:
        return _GPU_CACHE[ff]
    result: Optional[str] = None
    try:
        r = subprocess.run([ff, "-hide_banner", "-encoders"],
                           capture_output=True, text=True, timeout=30,
                           **_no_window_kwargs())
        for name in parse_encoders_list(r.stdout or ""):
            if _encoder_probe_ok(ff, name):
                result = name
                break
    except Exception:
        result = None
    _GPU_CACHE[ff] = result
    return result


def video_encoder_args(encoder: Optional[str] = None) -> List[str]:
    """ffmpeg video-encode flags for the chosen encoder.

    None (or unknown) -> CPU libx264 crf 18 preset veryfast.
    GPU encoders use a comparable constant-quality setting:
    NVENC p4 + CQ 19, Quick Sync medium + ICQ 19, AMF balanced + CQP 19.
    """
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "19",
                "-pix_fmt", "yuv420p"]
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "medium",
                "-global_quality", "19", "-pix_fmt", "yuv420p"]
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp",
                "-qp_i", "19", "-qp_p", "19", "-qp_b", "19",
                "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p"]


# --------------------------------------------------------------------------
# Effects
# --------------------------------------------------------------------------

EFFECTS = ("zoom_in", "zoom_out", "zoom_breathe", "pan_left", "pan_right",
           "pan_up", "shake_soft", "zoom_shake")

# Intensity presets: zoom_max (relative zoom at peak), shake_amp (px at
# 1080p width 1920, scaled proportionally for other widths),
# shake_freq (Hz). "Lembut banget" is the gentlest, "Guncang" the strongest.
INTENSITY_PRESETS = {
    "Lembut banget": {"zoom": 1.06, "shake": 5.0, "freq": 1.2},
    "Lembut": {"zoom": 1.12, "shake": 10.0, "freq": 1.6},
    "Guncang": {"zoom": 1.20, "shake": 22.0, "freq": 2.8},
}
INTENSITIES = tuple(INTENSITY_PRESETS.keys())
DEFAULT_INTENSITY = "Lembut"

EFFECT_LABELS = {
    "zoom_in": "Zoom In",
    "zoom_out": "Zoom Out",
    "zoom_breathe": "Zoom Napas (masuk-keluar)",
    "pan_left": "Pan Kiri",
    "pan_right": "Pan Kanan",
    "pan_up": "Pan Atas",
    "shake_soft": "Guncang Lembut",
    "zoom_shake": "Zoom + Guncang",
}


def _even(n: float) -> int:
    """Round to nearest even int (yuv420p needs even dimensions)."""
    return max(2, int(round(n / 2.0)) * 2)


def build_effect_filter(width: int, height: int, effect: str,
                        intensity: str = DEFAULT_INTENSITY,
                        duration: float = 5.0, fps: float = 30.0) -> str:
    """ffmpeg -vf string for one effect on one clip.

    Uses the `zoompan` filter — the canonical ffmpeg way to do smooth
    zoom. (The first attempt used scale+crop with a time-varying crop
    window, but crop's w/h are evaluated ONCE at filter init, so `t`
    in w/h fails with "Error when evaluating the expression" — zoom
    via crop is impossible; pan/shake via crop x/y worked, zoom did
    not. zoompan evaluates z/x/y per output frame, so it does all 8.)

    Each clip is rendered in its own ffmpeg call, so zoompan's output
    frame counter `on` starts at 0 for the clip. Total frames
    N = round(duration * fps); zoom/pan progress is on/N, shake uses
    on/fps as time in seconds. All offsets are clamped to the
    available margin (min(amp, margin/2*0.9) or a fraction of the
    margin), so the zoom window can never leave the frame.
    z/x/y expressions are single-quoted inside the filter string so
    commas inside min(...) survive the filter parser.
    """
    if effect not in EFFECTS:
        raise ValueError(f"efek tidak dikenal: {effect}")
    preset = INTENSITY_PRESETS.get(intensity, INTENSITY_PRESETS[DEFAULT_INTENSITY])
    zoom_max = float(preset["zoom"])
    shake_amp = float(preset["shake"])
    freq = float(preset["freq"])
    dur = max(0.1, float(duration))
    fps_i = max(1, int(round(fps))) if fps and fps > 0 else 30
    n_frames = max(1, int(round(dur * fps_i)))
    w = _even(width)
    h = _even(height)
    # Shake amplitude in input-frame pixels: preset px at 1920 wide,
    # scaled proportionally to this width.
    amp = shake_amp * (w / 1920.0)
    z = f"{zoom_max:.4f}"
    n = str(n_frames)
    f = f"{freq:.2f}"
    # Zoom factor over time, per effect. `on` = output frame counter.
    if effect == "zoom_in":
        zt = f"(1+({z}-1)*on/{n})"
    elif effect == "zoom_out":
        zt = f"({z}-({z}-1)*on/{n})"
    elif effect == "zoom_breathe":
        zt = f"(1+({z}-1)*(0.5-0.5*cos(2*PI*on/{n})))"
    elif effect == "zoom_shake":
        zt = f"(1+({z}-1)*on/{n})"
    else:
        # Pan / shake: hold a mid zoom so there is margin to move.
        z_mid = 1.0 + (zoom_max - 1.0) * 0.5
        zt = f"{z_mid:.4f}"

    # Centred zoom window: x/y of the top-left corner.
    cx = "(iw-iw/zoom)/2"
    cy = "(ih-ih/zoom)/2"
    # Shake offsets (same shape for shake_soft and zoom_shake).
    shake_x = (f"{cx}+sin(2*PI*{f}*on/{fps_i})*"
               f"min({amp:.1f},(iw-iw/zoom)/2*0.9)")
    shake_y = (f"{cy}+cos(2*PI*{f}*0.83*on/{fps_i})*"
               f"min({amp * 0.7:.1f},(ih-ih/zoom)/2*0.9)")

    if effect == "pan_left":
        x_expr = f"{cx}+(iw-iw/zoom)/2*0.85*(2*on/{n}-1)"
        y_expr = cy
    elif effect == "pan_right":
        x_expr = f"{cx}-(iw-iw/zoom)/2*0.85*(2*on/{n}-1)"
        y_expr = cy
    elif effect == "pan_up":
        x_expr = cx
        y_expr = f"{cy}+(ih-ih/zoom)/2*0.85*(2*on/{n}-1)"
    elif effect in ("shake_soft", "zoom_shake"):
        x_expr = shake_x
        y_expr = shake_y
    else:  # zoom_in / zoom_out / zoom_breathe: centred window
        x_expr = cx
        y_expr = cy

    return (
        f"zoompan=z='{zt}':d=1:x='{x_expr}':y='{y_expr}':"
        f"s={w}x{h}:fps={fps_i},format=yuv420p"
    )


# --------------------------------------------------------------------------
# Clip planning (pure logic)
# --------------------------------------------------------------------------

def plan_clips(total: float, min_dur: float, max_dur: float,
               rng: Optional[random.Random] = None) -> List[float]:
    """Split `total` seconds into clip durations.

    Each duration is random uniform in [min_dur, max_dur], except the
    tail: if the remainder after the last full clip is < min_dur, it
    is MERGED into the last clip (last clip may grow to at most
    max_dur + min_dur). Never emits a tiny <min_dur clip, except when
    the whole video itself is shorter than min_dur (one clip = whole
    video). The durations sum to `total` (within float rounding).
    """
    if total <= 0:
        return []
    if min_dur <= 0 or max_dur < min_dur:
        raise ValueError(f"min/max durasi tidak valid: {min_dur}/{max_dur}")
    if total <= min_dur:
        return [float(total)]
    r = rng or random
    durations: List[float] = []
    remaining = float(total)
    while remaining > max_dur:
        # Pick d so the leftover stays >= min_dur (or gets merged later).
        upper = min(max_dur, remaining - min_dur)
        d = r.uniform(min_dur, upper)
        durations.append(d)
        remaining -= d
    if remaining >= min_dur:
        durations.append(remaining)
    else:
        # Tail remainder < min_dur: merge into the last clip.
        if durations:
            durations[-1] += remaining
        else:
            durations.append(remaining)
    return durations


def assign_effects(n: int, rng: Optional[random.Random] = None) -> List[str]:
    """Assign one effect per clip from the shuffled 8-effect pool.

    The pool is shuffled, used in full, then reshuffled for the next
    cycle — so no effect repeats until all 8 have been used once.
    Adjacent clips never share an effect, including across a cycle
    boundary (fixed by swapping the first two of the new cycle).
    """
    if n <= 0:
        return []
    r = rng or random
    out: List[str] = []
    while len(out) < n:
        cycle = list(EFFECTS)
        r.shuffle(cycle)
        if out and cycle[0] == out[-1]:
            cycle[0], cycle[1] = cycle[1], cycle[0]
        out.extend(cycle)
    return out[:n]


# --------------------------------------------------------------------------
# Random output names
# --------------------------------------------------------------------------

_NAME_CHARS = string.ascii_lowercase + string.digits


def random_output_name(rng: Optional[random.Random] = None,
                       length: int = 10) -> str:
    """Random filename stem, e.g. 'a7k9x2q4m1' — never sequential."""
    r = rng or random
    return "".join(r.choice(_NAME_CHARS) for _ in range(length))


def unique_random_output_path(folder: str,
                              rng: Optional[random.Random] = None,
                              length: int = 10) -> str:
    """Random .mp4 path in `folder` that does not exist yet
    (regenerate on collision)."""
    while True:
        cand = os.path.join(folder, random_output_name(rng, length) + ".mp4")
        if not os.path.exists(cand):
            return cand


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_clip(input_path: str, start: float, duration: float,
                output_path: str, effect: str,
                intensity: str = DEFAULT_INTENSITY,
                width: int = 0, height: int = 0, fps: float = 30.0,
                encoder: Optional[str] = None,
                log: LogFn = _noop_log,
                ffmpeg: Optional[str] = None) -> bool:
    """Render ONE clip: -ss start, -t duration, effect filter,
    audio removed totally (-an), re-encode at high quality.

    "Sikat aja": success = ffmpeg exit 0 + output file exists
    and is non-empty. No probe-based verification.
    """
    ff = find_ffmpeg(ffmpeg)
    if width <= 0 or height <= 0:
        log("  render gagal: ukuran video tidak diketahui (probe gagal)")
        return False
    try:
        vf = build_effect_filter(width, height, effect, intensity, duration, fps)
    except ValueError as e:
        log(f"  render gagal: {e}")
        return False
    v_args = video_encoder_args(encoder)
    cmd = ([ff, "-hide_banner", "-y",
            "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
            "-i", input_path,
            "-vf", vf, "-an"] + v_args +
           ["-movflags", "+faststart", output_path])
    r = _run(cmd, log)
    return (r.returncode == 0 and os.path.isfile(output_path)
            and os.path.getsize(output_path) > 0)
