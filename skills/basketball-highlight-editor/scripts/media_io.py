"""Bounded FFmpeg media I/O. Presentation seconds, autorotation and CFR output.

No implicit normalization/transcoding of source files. FFmpeg does accurate
input seeking; the fps filter keeps timestamps relative to the requested seek.
"""
import hashlib
import json
import math
import os
import subprocess
from fractions import Fraction
from pathlib import Path

THREADS = 2
RENDER_SCHEMA = 3


def command(args, timeout=180, binary=False):
    try:
        result = subprocess.run([str(x) for x in args], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError as exc:
        raise ValueError('MEDIA_TOOL_MISSING: install FFmpeg/FFprobe and add it to PATH') from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError('MEDIA_TIMEOUT: reduce the processed range or increase the explicit timeout') from exc
    if result.returncode:
        error = result.stderr.decode(errors='replace')[-1800:]
        raise ValueError('MEDIA_DECODE_FAILED: file may be truncated or use an unavailable codec; '
                         'restore the original or re-encode with FFmpeg. ' + error)
    return result.stdout if binary else result.stdout.decode(errors='replace')


def rate(value):
    try:
        f = Fraction(value)
        return f if 0 < f <= 240 else None
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def probe(path, validate=True):
    path = Path(path)
    if not path.is_file():
        raise ValueError('MEDIA_NOT_FOUND: provide an existing local video')
    if path.stat().st_size == 0:
        raise ValueError('MEDIA_EMPTY: zero-byte input; copy/export the source again')
    raw = command(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path])
    try:
        data = json.loads(raw)
        video = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
        if not video:
            raise ValueError('MEDIA_NO_VIDEO: input has no video stream; choose a movie file')
        width, height = int(video['width']), int(video['height'])
        durations = []
        # The video stream determines the picture timeline, not a longer song.
        for x in (video.get('duration'), data.get('format', {}).get('duration')):
            try:
                x = float(x)
                if math.isfinite(x) and x > 0:
                    durations.append(x)
            except (ValueError, TypeError):
                pass
        if not durations or width <= 0 or height <= 0:
            raise ValueError('MEDIA_INVALID_DURATION: no positive video duration; export a playable source')
        duration = durations[0]
        fps = rate(video.get('r_frame_rate')) or rate(video.get('avg_frame_rate'))
        if fps is None:
            raise ValueError('MEDIA_INVALID_FRAME_RATE: missing/unsupported timestamps; remux or re-encode the source')
        rotation = float(video.get('tags', {}).get('rotate', 0))
        for side in video.get('side_data_list', []):
            if 'rotation' in side:
                rotation = float(side['rotation'])
        rotation = int(round(rotation)) % 360
        if rotation not in (0, 90, 180, 270):
            raise ValueError('MEDIA_UNSUPPORTED_ROTATION: export an upright copy for non-right-angle rotation')
        display_w, display_h = (height, width) if rotation in (90, 270) else (width, height)
        has_audio = any(s.get('codec_type') == 'audio' for s in data.get('streams', []))
        result = {'duration': duration, 'width': display_w, 'height': display_h,
                  'coded_width': width, 'coded_height': height, 'rotation': rotation,
                  'fps': str(fps), 'render_fps': str(fps), 'has_audio': has_audio,
                  'codec': video.get('codec_name', 'unknown'),
                  'time_base': video.get('time_base'), 'presentation_start': float(video.get('start_time', 0) or 0)}
    except (KeyError, TypeError, StopIteration) as exc:
        raise ValueError('MEDIA_INVALID_METADATA: cannot read video dimensions/timestamps; export a new copy') from exc
    if validate:
        # Bounded head/tail decode detects typical faststart truncation without
        # decoding an entire two-hour file at every project load.
        for t in sorted({0.0, max(0.0, duration - min(1.0, duration / 2))}):
            frame = command(['ffmpeg', '-v', 'error', '-xerror', '-err_detect', 'explode',
                '-threads', THREADS, '-seek_timestamp', '1', '-ss', f'{t + result["presentation_start"]:.9f}', '-i', path, '-map', '0:v:0',
                '-frames:v', 1, '-vf', 'scale=16:16', '-filter_threads', 1,
                '-pix_fmt', 'gray', '-f', 'rawvideo', '-'], timeout=60, binary=True)
            if len(frame) != 256:
                raise ValueError('MEDIA_TRUNCATED: declared video tail cannot be decoded; restore the complete original')
    return result


def frame_bgr(path, seconds, meta=None, max_width=None):
    import numpy as np
    meta = meta or probe(path, validate=False)
    width, height = meta['width'], meta['height']
    if max_width and width > max_width:
        scale = max_width / width; width = max_width; height = max(2, int(round(height * scale)))
    payload = command(['ffmpeg', '-v', 'error', '-threads', THREADS,
                       '-seek_timestamp', '1', '-ss', f'{seconds + meta.get("presentation_start", 0):.9f}', '-i', path, '-map', '0:v:0', '-an',
                       '-frames:v', 1, '-vf', f'scale={width}:{height}', '-filter_threads', 1,
                       '-pix_fmt', 'bgr24', '-f', 'rawvideo', '-'], binary=True)
    if len(payload) != width * height * 3:
        raise ValueError('FRAME_DECODE_FAILED: requested presentation time has no complete picture')
    return np.frombuffer(payload, dtype=np.uint8).reshape(height, width, 3).copy()


def output_rate(source):
    return rate(source.get('render_fps')) or rate(source.get('fps')) or Fraction(30)


def frames_for(duration, fps):
    return max(1, int(math.floor(float(Fraction(str(duration)) * fps) + .5)))


def render(source, meta, start, end, out, frame_count=None):
    fps = output_rate(meta)
    count = frame_count if frame_count is not None else frames_for(end-start, fps)
    if count < 1:
        raise ValueError('CLIP_SHORTER_THAN_ONE_FRAME: increase the clip duration')
    duration = float(Fraction(count, 1) / fps)
    # Absolute seeking is anchored to video presentation_start, not an earlier
    # Opus priming timestamp in the container. Seeking timestamps stay relative to requested start. Do not shift the
    # first retained VFR frame to zero before temporal resampling.
    vf = (f'fps=fps={fps}:start_time=0:round=near:eof_action=pass,'
          'scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,'
          'pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1')
    cmd = ['ffmpeg', '-v', 'error', '-threads', THREADS, '-seek_timestamp', '1', '-ss', f'{start + meta.get("presentation_start", 0):.9f}', '-i', source,
           '-map', '0:v:0', '-map', '0:a:0?', '-vf', vf, '-filter_threads', 1,
           '-frames:v', count, '-t', f'{duration:.9f}', '-c:v', 'libx264', '-threads', THREADS,
           '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p']
    if meta.get('has_audio'):
        cmd += ['-af', f'aresample=48000:async=1:first_pts=0,apad,atrim=duration={duration:.9f}',
                '-c:a', 'aac', '-ar', '48000', '-ac', 2]
    cmd += ['-map_metadata', '-1', '-metadata', 'creation_time=1970-01-01T00:00:00Z',
            '-movflags', '+faststart', '-y', out]
    command(cmd, timeout=max(180, int(duration * 3)))
    return {'fps': str(fps), 'frames': count, 'duration': duration}
