from core.logger import log
from core.exits import exit_signal
from core.ledger import PaperLedger
from core.sage import Sage


class Raphael:
    """The supreme brain. Raphael thinks and executes. Aegis guards. Master Mohamad commands."""

    RISK_AGENT = "Aegis"
    ALIASES = {"Strategy": "Strategist"}

    def __init__(self, ledger=None):
        self.agents = {}
        self.sage = Sage()
        self.ledger = ledger or PaperLedger()

    def register(self, agent):
        self.agents[agent.name] = agent
        log(f"RAPHAEL registered {agent.name} ({agent.division})")

    def dispatch(self, agent_name, task):
        if agent_name not in self.agents:
            raise KeyError(f"No agent named {agent_name}")
        log(f"RAPHAEL -> {agent_name}: {task}")
        result = self.agents[agent_name].handle(task)
        log(f"{agent_name} -> RAPHAEL: {result}")
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
                closed.append({**record, "exit_reason": reason})
        return closed

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
        executed = approved and recommendation["action"] != "hold"
        if executed and trade:
            record = self.ledger.open_trade(
                symbol=task.get("symbol"),
                side=trade.get("side", "buy"),
                size=trade["size"],
                entry=trade["entry"],
                stop_loss=trade["stop_loss"],
            )
            log(f"RAPHAEL recorded paper trade #{record['id']} in ledger")
        decision = {
            "goal": goal,
            "recommendation": recommendation,
            "risk": risk,
            "executed": executed,
        }
        log(f"RAPHAEL final decision: {decision}")
        print(f"Final decision: {decision}")
        return decision
