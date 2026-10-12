"""The paper trial: real market days on pretend money, judged by fixed rules.

    python trial.py start   # begin a new trial (Treasury restarts at ACCOUNT_SIZE)
    python trial.py         # rebuild the scorecard and open it in the browser

The scorecard also updates by itself at the end of every market day.
Rules live in config/settings.py (TRIAL_*).
"""
import sys
import webbrowser

from core import trial


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["start"]:
        if trial.load() and "--force" not in argv:
            print("A trial is already running. Use `python trial.py start --force` to start over.")
            return 1
        t = trial.start()
        print(f"Trial started {t['started']}: {t['days']} market days on pretend money.")
        print("The Treasury starts fresh. Each market day updates the scorecard by itself.")
        trial.update()
        return 0

    result = trial.update()
    if result is None:
        print("No trial yet. Start one with: python trial.py start")
        return 1
    s, v = result
    print(f"Trial: day {v['days_done']} of {v['days_total']} | {v['status'].upper()} | "
          f"P&L {'+' if s['pnl'] >= 0 else '-'}${abs(s['pnl']):,.2f} | {s['trades']} trades")
    for label, ok, detail in v["checks"]:
        print(f"  {'PASS' if ok else 'FAIL'}  {label} ({detail})")
    if v["replace"]:
        print(f"  Agents to replace: {', '.join(v['replace'])}")
    page = (trial.TRIAL_DIR / "scorecard.html").resolve()
    print(f"Scorecard: {page}")
    if "--no-open" not in argv:
        webbrowser.open(page.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
