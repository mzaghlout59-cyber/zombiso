"""Clipper: subtitles parse, moments snap to sentences, and a real clip comes out 1080x1920 with captions."""
import json
import shutil
import subprocess

import pytest

from clipper import clip

VTT = """WEBVTT

00:00:00.000 --> 00:00:04.000
<c>so</c> here is the thing

00:00:04.000 --> 00:00:09.000
so here is the thing
nobody tells you this

00:00:09.000 --> 00:00:15.000
nobody tells you this
and it changed everything
"""

SEGMENTS = [{"start": float(i * 5), "end": float(i * 5 + 5), "text": f"sentence number {i}"} for i in range(30)]


def test_parse_vtt_drops_tags_and_rolling_repeats():
    segs = clip.parse_subs(VTT)
    assert [s["text"] for s in segs] == ["so here is the thing", "nobody tells you this", "and it changed everything"]
    assert segs[2]["start"] == 9.0 and segs[2]["end"] == 15.0


def test_parse_srt():
    srt = "1\n00:01:02,500 --> 00:01:04,000\nHello there\n\n2\n00:01:04,000 --> 00:01:06,000\nFriend\n"
    assert clip.parse_subs(srt) == [{"start": 62.5, "end": 64.0, "text": "Hello there"},
                                    {"start": 64.0, "end": 66.0, "text": "Friend"}]


def test_snap_aligns_to_sentences_and_respects_length():
    m = clip.snap({"start": 12.3, "end": 200.0}, SEGMENTS, 20, 60)
    assert m["start"] == 10.0 and m["end"] == 70.0  # capped at 60s, on a sentence end
    m = clip.snap({"start": 31.0, "end": 33.0}, SEGMENTS, 20, 60)
    assert m["start"] == 30.0 and m["end"] == 50.0  # stretched to the minimum


def test_pick_moments_drops_overlaps():
    def fake_ask(system, prompt, schema, **kw):
        assert "[5.0-10.0] sentence number 1" in prompt
        base = {"title": "t", "caption": "c", "hashtags": ["x"], "why": "w"}
        return {"clips": [{**base, "start": 10, "end": 40}, {**base, "start": 20, "end": 50},
                          {**base, "start": 60, "end": 90}]}
    picked = clip.pick_moments(SEGMENTS, 5, 20, 60, ask=fake_ask)
    assert [(m["start"], m["end"]) for m in picked] == [(10.0, 40.0), (60.0, 90.0)]


def test_words_spread_evenly_without_word_timings():
    words = clip.words_between([{"start": 0.0, "end": 4.0, "text": "one two three four"}], 0, 10)
    assert words == [(0.0, "one"), (1.0, "two"), (2.0, "three"), (3.0, "four")]


def test_captions_group_words():
    ass = clip.captions_ass([(0.0, "a"), (0.5, "b"), (1.0, "c"), (1.5, "d")], 5)
    assert "Dialogue: 0,0:00:00.00,0:00:01.50,Cap,,0,0,0,,A B C" in ass
    assert "Dialogue: 0,0:00:01.50,0:00:03.00,Cap,,0,0,0,,D" in ass


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.parametrize("fit", ["crop", "blur"])
def test_cut_makes_vertical_clip(tmp_path, fit):
    video = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", "12", "-shortest",
                    "-c:v", "libx264", "-c:a", "aac", str(video)], check=True)
    segs = [{"start": 0.0, "end": 12.0, "text": "this is a test of the captions"}]
    out = clip.cut(video, {"start": 2.0, "end": 8.0, "title": "Big Test!"}, segs, tmp_path, 1, fit)
    assert out.name == "01-big-test.mp4" and not (tmp_path / "01.ass").exists()
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out)],
                                      capture_output=True, text=True, check=True).stdout)
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert abs(float(probe["format"]["duration"]) - 6.0) < 0.5
