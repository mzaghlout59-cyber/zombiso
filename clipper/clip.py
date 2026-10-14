"""Turn a long video into short vertical clips with captions, ready for TikTok / Shorts / Reels.

    python clipper/clip.py podcast.mp4
    python clipper/clip.py "https://www.youtube.com/watch?v=..." --clips 8 --max 45
    python clipper/clip.py talk.mp4 --subs talk.srt --fit blur

1. Transcript: local Whisper (pip install faster-whisper), or a .srt/.vtt you pass
   with --subs, or the video's own subtitles when it was downloaded from a link.
2. Claude reads the transcript and picks the moments most likely to go viral,
   each with a title, a caption and hashtags.
3. ffmpeg cuts each moment to 1080x1920 (centre crop, or --fit blur to keep the
   whole frame over a blurred background) and burns in big word-by-word captions.

Everything lands in clipper/out/<video name>/: clips/*.mp4 plus clips.md with the
text to paste when posting. Only clip videos you have permission to use (your own,
or a creator's clipping program).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from anywhere

OUT = Path(__file__).resolve().parent / "out"
WORDS_PER_CAPTION = 3

SYSTEM = """You are an expert short-form video editor who finds the moments in long videos
that go viral as TikTok / YouTube Shorts / Reels clips. A great clip has a strong hook in
its first 3 seconds, stands on its own without context, and ends on a payoff: a punchline,
a surprising fact, a strong opinion, an emotional moment or a useful tip. Never cut
mid-sentence. Write titles and captions in the language of the video."""

SCHEMA = {
    "type": "object",
    "properties": {"clips": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "start": {"type": "number", "description": "seconds"},
            "end": {"type": "number", "description": "seconds"},
            "title": {"type": "string", "description": "short, punchy, under 60 characters"},
            "caption": {"type": "string", "description": "post caption, 1-2 sentences"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
            "why": {"type": "string", "description": "why this moment works"},
        },
        "required": ["start", "end", "title", "caption", "hashtags", "why"],
        "additionalProperties": False,
    }}},
    "required": ["clips"],
    "additionalProperties": False,
}


# ---------- transcript ----------

def _seconds(stamp):
    parts = stamp.replace(",", ".").split(":")
    return sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))


def parse_subs(text):
    """Segments [{start, end, text}] from SRT or WebVTT, YouTube auto-captions included."""
    segments, previous = [], set()
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        m = re.search(r"([\d:.,]+)\s*-->\s*([\d:.,]+)", block)
        if not m:
            continue
        lines = block[m.end():].split("\n")[1:]
        lines = [re.sub(r"<[^>]+>", "", l).strip() for l in lines]
        lines = [l for l in lines if l]
        # YouTube's rolling captions repeat the previous cue's line; keep only new lines
        new = [l for l in lines if l not in previous]
        previous = set(lines)
        if new:
            segments.append({"start": _seconds(m.group(1)), "end": _seconds(m.group(2)), "text": " ".join(new)})
    return segments


def transcribe(video, model="small"):
    """Segments with word timings from local Whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("No transcript: run `pip install faster-whisper`, or pass --subs file.srt")
    print(f"Transcribing with Whisper ({model}); a 1-hour video takes a few minutes ...")
    segs, _ = WhisperModel(model, device="auto", compute_type="int8").transcribe(str(video), word_timestamps=True)
    return [{"start": s.start, "end": s.end, "text": s.text.strip(),
             "words": [{"start": w.start, "end": w.end, "word": w.word.strip()} for w in (s.words or [])]}
            for s in segs]


def words_between(segments, start, end):
    """(time, word) pairs inside [start, end]; segments without word timings are spread evenly."""
    out = []
    for seg in segments:
        if seg["end"] <= start or seg["start"] >= end:
            continue
        words = seg.get("words") or []
        if not words:
            parts = seg["text"].split()
            step = (seg["end"] - seg["start"]) / max(len(parts), 1)
            words = [{"start": seg["start"] + i * step, "word": w} for i, w in enumerate(parts)]
        out += [(w["start"], w["word"]) for w in words if start <= w["start"] < end and w["word"]]
    return out


# ---------- picking moments ----------

def transcript_prompt(segments, n, min_s, max_s):
    lines = "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segments)
    return (f"Pick the {n} best clips from this transcript, best first. Each clip must be "
            f"{min_s}-{max_s} seconds long and must not overlap another. Use the timestamps "
            f"(seconds) shown.\n\n{lines}")


def snap(moment, segments, min_s, max_s):
    """Align a moment to whole sentences and keep it within [min_s, max_s] seconds."""
    starts = [s["start"] for s in segments if s["start"] <= moment["start"] + 0.5]
    start = max(starts) if starts else segments[0]["start"]
    ends = [s["end"] for s in segments if start + min_s <= s["end"] <= start + max_s]
    target = max(moment["end"], start + min_s)
    end = min(ends, key=lambda e: abs(e - target)) if ends else min(start + max_s, segments[-1]["end"])
    return {**moment, "start": round(start, 2), "end": round(end, 2)}


def pick_moments(segments, n, min_s, max_s, ask=None):
    if ask is None:
        from core.llm import ask_json as ask
    print("Claude is picking the best moments ...")
    found = ask(SYSTEM, transcript_prompt(segments, n, min_s, max_s), SCHEMA,
                effort="medium", max_tokens=8000)["clips"]
    picked = []
    for m in found:
        m = snap(m, segments, min_s, max_s)
        if m["end"] - m["start"] >= min_s * 0.5 and all(m["end"] <= p["start"] or m["start"] >= p["end"] for p in picked):
            picked.append(m)
    return picked[:n]


# ---------- cutting ----------

def _ass_time(t):
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def captions_ass(words, clip_len):
    """ASS subtitles: a few words at a time, big and bold, in the lower middle of a 1080x1920 frame."""
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial,88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,60,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    chunks = [words[i:i + WORDS_PER_CAPTION] for i in range(0, len(words), WORDS_PER_CAPTION)]
    for i, chunk in enumerate(chunks):
        start = chunk[0][0]
        end = chunks[i + 1][0][0] if i + 1 < len(chunks) else min(start + 1.5, clip_len)
        text = " ".join(w for _, w in chunk).upper().replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Cap,,0,0,0,,{text}")
    return head + "\n".join(lines) + "\n"


def video_filter(fit, ass_name):
    if fit == "blur":
        return ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                "boxblur=30[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,"
                f"subtitles={ass_name}")
    return f"crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920,setsar=1,subtitles={ass_name}"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "clip"


def cut(video, moment, segments, folder, index, fit):
    length = moment["end"] - moment["start"]
    words = [(t - moment["start"], w) for t, w in words_between(segments, moment["start"], moment["end"])]
    ass = f"{index:02d}.ass"
    (folder / ass).write_text(captions_ass(words, length), encoding="utf-8")
    out = f"{index:02d}-{slug(moment['title'])}.mp4"
    # run inside the folder so the subtitles path has no drive letter (ffmpeg filter escaping on Windows)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{moment['start']:.2f}", "-t", f"{length:.2f}",
           "-i", str(Path(video).resolve()), "-vf", video_filter(fit, ass),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", out]
    subprocess.run(cmd, cwd=folder, check=True)
    (folder / ass).unlink()
    return folder / out


# ---------- the whole job ----------

def download(url, work):
    if not shutil.which("yt-dlp"):
        raise SystemExit("To clip from a link, first: pip install yt-dlp")
    print("Downloading ...")
    subprocess.run(["yt-dlp", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4",
                    "--write-subs", "--write-auto-subs", "--sub-langs", "en.*,pt.*,es.*,ar.*", "--sub-format", "vtt",
                    "-o", str(work / "source.%(ext)s"), url], check=True)
    return work / "source.mp4", next(iter(sorted(work.glob("source*.vtt"))), None)


def write_notes(moments, files, folder):
    lines = ["# Clips\n"]
    for m, f in zip(moments, files):
        tags = " ".join("#" + t.lstrip("#") for t in m["hashtags"])
        lines.append(f"## {f.name}\n\n**{m['title']}**  ({m['start']:.0f}s – {m['end']:.0f}s)\n\n"
                     f"{m['caption']}\n\n{tags}\n\n_Why: {m['why']}_\n")
    (folder / "clips.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="a video file, or a link to one (needs yt-dlp)")
    ap.add_argument("--clips", type=int, default=5, help="how many clips (default 5)")
    ap.add_argument("--min", type=int, default=20, help="shortest clip, seconds")
    ap.add_argument("--max", type=int, default=60, help="longest clip, seconds")
    ap.add_argument("--fit", choices=["crop", "blur"], default="crop",
                    help="crop: fill the frame from the centre; blur: whole frame over a blurred copy")
    ap.add_argument("--subs", type=Path, help="use this .srt/.vtt instead of transcribing")
    ap.add_argument("--whisper-model", default="small", help="tiny/base/small/medium/large-v3")
    args = ap.parse_args(argv)
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is needed: winget install ffmpeg (Windows) or brew install ffmpeg")

    is_url = args.source.startswith(("http://", "https://"))
    name = slug(re.sub(r"^https?://", "", args.source)) if is_url else Path(args.source).stem
    work = OUT / name
    work.mkdir(parents=True, exist_ok=True)
    video, subs = (download(args.source, work) if is_url else (Path(args.source), None))
    subs = args.subs or subs

    cache = work / "transcript.json"
    if cache.exists():
        segments = json.loads(cache.read_text(encoding="utf-8"))
    else:
        segments = parse_subs(subs.read_text(encoding="utf-8")) if subs else transcribe(video, args.whisper_model)
        cache.write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")
    if not segments:
        raise SystemExit("The transcript is empty: is there speech in this video?")

    moments = pick_moments(segments, args.clips, args.min, args.max)
    clips = work / "clips"
    clips.mkdir(exist_ok=True)
    files = []
    for i, m in enumerate(moments, 1):
        print(f"Cutting {i}/{len(moments)}: {m['title']}")
        files.append(cut(video, m, segments, clips, i, args.fit))
    write_notes(moments, files, clips)
    print(f"Done: {len(files)} clips in {clips}  (titles and captions in clips.md)")


if __name__ == "__main__":
    sys.exit(main())
