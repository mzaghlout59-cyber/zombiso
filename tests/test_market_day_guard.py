"""market_day must never trade the same day twice or run two copies at once."""
import json
import os

import market_day


def make_run(runs, name, source="alpaca", finished=True):
    d = runs / name
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"source": source}))
    if finished:
        (d / "audit.json").write_text('{"ok": true}')
    return d


def test_traded_today_needs_a_finished_market_run_from_today(tmp_path):
    runs = tmp_path / "runs"
    assert market_day.traded_today(runs, "20261013") is False
    make_run(runs, "20261013-103018-000000", finished=False)        # cut short by a restart
    make_run(runs, "20261013-120000-000000", source="simulated")     # a practice run
    make_run(runs, "20261012-105400-000000")                          # yesterday
    assert market_day.traded_today(runs, "20261013") is False
    make_run(runs, "20261013-105415-000000")
    assert market_day.traded_today(runs, "20261013") is True


def test_lock_blocks_a_second_live_copy_but_not_a_stale_one(tmp_path):
    lock = tmp_path / "market_day.lock"
    assert market_day.take_lock(lock) is True             # nobody held it
    assert lock.read_text() == str(os.getpid())
    assert market_day.take_lock(lock) is False            # held by a live process (this one)
    lock.write_text("99999999")                            # a process that no longer exists
    assert market_day.take_lock(lock) is True
    lock.write_text("garbage")
    assert market_day.take_lock(lock) is True


def test_main_skips_when_the_day_is_already_done(monkeypatch, capsys):
    monkeypatch.setattr(market_day, "market_clock", lambda: {
        "is_open": True, "now": None, "next_open": None, "next_close": None})
    monkeypatch.setattr(market_day, "traded_today", lambda: True)
    assert market_day.main([]) == 0
    assert "already done" in capsys.readouterr().out
