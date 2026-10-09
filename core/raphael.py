from core.logger import log
from core.sage import Sage


class Raphael:
    """The supreme brain. Raphael thinks and executes. Aegis guards. Master Mohamad commands."""

    RISK_AGENT = "Aegis"
    ALIASES = {"Strategy": "Strategist"}

    def __init__(self):
        self.agents = {}
        self.sage = Sage()

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
        risk = self.dispatch(self.RISK_AGENT, risk_task)

        approved = risk.get("approved", False) is True
        decision = {
            "goal": goal,
            "recommendation": recommendation,
            "risk": risk,
            "executed": approved and recommendation["action"] != "hold",
        }
        log(f"RAPHAEL final decision: {decision}")
        print(f"Final decision: {decision}")
        return decision
