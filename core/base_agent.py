from core.logger import log


class BaseAgent:
    """Parent class for every worker agent in Zombiso AI City."""

    name = "BaseAgent"
    division = "Unassigned"
    rank = "Unassigned"       # Sovereign / Commander / Squad
    commander = None          # who this agent answers to
    alias = None              # in-world codename; falls back to name
    purpose = None            # one line: what this agent is for

    def handle(self, task):
        """Receive a task dict, return a result dict. Override in subclasses."""
        raise NotImplementedError(f"{self.name} has no handle() implemented")

    def profile(self):
        """Roster entry for this agent."""
        return {
            "name": self.name,
            "alias": self.alias or self.name,
            "division": self.division,
            "rank": self.rank,
            "commander": self.commander,
            "purpose": self.purpose or "(purpose not documented)",
        }

    def say(self, message):
        line = f"[{self.division}/{self.name}] {message}"
        print(line)
        log(line)
