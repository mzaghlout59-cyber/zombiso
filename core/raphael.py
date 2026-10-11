from config import settings
from core.clock import SimClock
from core.events import EventLog
from core.logger import log
from core.exits import exit_signal
from core.ledger import PaperLedger
from core.sage import Sage


class Raphael:
    """The supreme brain. Raphael thinks and executes. Aegis guards. Master Mohamad commands."""

    RISK_AGENT = "Aegis"
    ALIASES = {"Strategy": "Strategist"}
    BOOK_REPORTERS = ("PortfolioManager", "PerformanceAnalyst")  # Aegis's squad

    def __init__(self, ledger=None, clock=None, events=None):
        self.agents = {}
        self.sage = Sage()
        self.clock = clock or SimClock()
        self.ledger = ledger or PaperLedger(clock=self.clock)
        if self.ledger.clock is None:
            self.ledger.clock = self.clock
        self.events = events or EventLog(clock=self.clock)

    def register(self, agent):
        self.agents[agent.name] = agent
        log(f"RAPHAEL registered {agent.name} ({agent.division})")

    def dispatch(self, agent_name, task):
        if agent_name not in self.agents:
            raise KeyError(f"No agent named {agent_name}")
        shown = {k: (f"<{len(v)} trades>" if k == "trades" else v) for k, v in task.items()}
        log(f"RAPHAEL -> {agent_name}: {shown}")
        result = self.agents[agent_name].handle(task)
        log(f"{agent_name} -> RAPHAEL: {result}")
        self.events.emit("agent_report", agent=agent_name,
                         symbol=task.get("symbol"), result=result)
        return result

    def check_exits(self, prices):
        """Close any open paper trade whose price hit its stop or target.

        prices = {"AAPL": 102.5, ...}. Symbols with no price are skipped.
        Returns a list of closed-trade records.
        """
        closed = []
        for trade in self.ledger.open_trades():
            price = prices.get(trade["symbol"])
            if price is None:
                continue
            reason = exit_signal(trade, price)
            if reason:
                record = self.ledger.close_trade(trade["id"], price)
                log(f"RAPHAEL closed trade #{trade['id']} {trade['symbol']} "
                    f"at {price} ({reason}) pnl={record['pnl']}")
                self.events.emit("trade_closed", trade_id=record["id"], symbol=record["symbol"],
                                 side=record["side"], size=record["size"], entry=record["entry"],
                                 stop_loss=record["stop_loss"], exit=price,
                                 pnl=record["pnl"], reason=reason)
                closed.append({**record, "exit_reason": reason})
        return closed

    def tick(self, feed):
        """One market step: read current prices for open positions, run exits.

        feed is any PriceFeed. Symbols the feed cannot price are skipped safely.
        Returns the list of trades closed this tick.
        """
        prices = {}
        for trade in self.ledger.open_trades():
            sym = trade["symbol"]
            try:
                prices[sym] = feed.get_price(sym)
            except KeyError:
                log(f"RAPHAEL tick: no price for {sym}, skipping")
        return self.check_exits(prices)

    def close_all(self, feed, reason="end_of_day"):
        """Exit every open trade at the current price, e.g. at the market close."""
        closed = []
        for trade in self.ledger.open_trades():
            try:
                price = feed.get_price(trade["symbol"])
            except KeyError:
                log(f"RAPHAEL close_all: no price for {trade['symbol']}, left open")
                continue
            record = self.ledger.close_trade(trade["id"], price)
            log(f"RAPHAEL closed trade #{trade['id']} {trade['symbol']} at {price} ({reason}) "
                f"pnl={record['pnl']}")
            self.events.emit("trade_closed", trade_id=record["id"], symbol=record["symbol"],
                             side=record["side"], size=record["size"], entry=record["entry"],
                             stop_loss=record["stop_loss"], exit=price,
                             pnl=record["pnl"], reason=reason)
            closed.append({**record, "exit_reason": reason})
        return closed

    def review(self):
        """End of cycle: Ledgerkeeper and Scorekeeper report on the books to Aegis.

        Returns {agent_name: report}. Reports only; nothing here changes a trade.
        """
        task = {"trades": self.ledger.trades}
        return {name: self.dispatch(name, task)
                for name in self.BOOK_REPORTERS if name in self.agents}

    def roster(self):
        for agent in self.agents.values():
            print(f"{agent.division:12} | {agent.name}")

    def run_goal(self, goal, task):
        """Full flow: Sage plans, Raphael executes, Sage recommends, Aegis decides."""
        print(f"\n=== GOAL: {goal} ===")

        # 1. Sage plans
        steps = self.sage.plan(goal)
        print(f"Sage plan: {steps}")

        # 2. Raphael executes the plan
        results = {}
        for step in steps:
            results[step] = self.dispatch(self.ALIASES.get(step, step), task)

        # 3. Sage recommends
        recommendation = self.sage.recommend(results)
        print(f"Sage recommendation: {recommendation}")

        # 4. Aegis has the final, deterministic say
        trade = (results.get("Strategy") or {}).get("trade")
        risk_task = {**task, "recommendation": recommendation, "trade": trade}
        aegis = self.agents[self.RISK_AGENT]
        aegis.open_positions = self.ledger.open_positions()
        aegis.daily_pnl = self.ledger.daily_pnl()
        aegis.open_symbols = self.ledger.open_symbols()
        risk = self.dispatch(self.RISK_AGENT, risk_task)

        approved = risk.get("approved", False) is True
        confident = recommendation["confidence"] >= settings.MIN_SAGE_CONFIDENCE
        if approved and not confident:
            log(f"RAPHAEL skipped trade: Sage confidence {recommendation['confidence']} "
                f"below {settings.MIN_SAGE_CONFIDENCE}")
        executed = approved and confident and recommendation["action"] != "hold"
        self.events.emit("decision", symbol=task.get("symbol"),
                         action=recommendation["action"],
                         confidence=recommendation["confidence"],
                         approved=approved, risk_reason=risk.get("reason"),
                         executed=bool(executed and trade))
        if executed and trade:
            record = self.ledger.open_trade(
                symbol=task.get("symbol"),
                side=trade.get("side", "buy"),
                size=trade["size"],
                entry=trade["entry"],
                stop_loss=trade["stop_loss"],
            )
            log(f"RAPHAEL recorded paper trade #{record['id']} in ledger")
            self.events.emit("trade_opened", trade_id=record["id"], symbol=record["symbol"],
                             side=record["side"], size=record["size"], entry=record["entry"],
                             stop_loss=record["stop_loss"])
        decision = {
            "goal": goal,
            "recommendation": recommendation,
            "risk": risk,
            "executed": executed,
        }
        log(f"RAPHAEL final decision: {decision}")
        print(f"Final decision: {decision}")
        return decision
