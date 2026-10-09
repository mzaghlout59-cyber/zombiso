from core.logger import log


class BaseAgent:
    """Parent class for every worker agent in Zombiso AI City."""

    name = "BaseAgent"
    division = "Unassigned"

    def handle(self, task):
        """Receive a task dict, return a result dict. Override in subclasses."""
        raise NotImplementedError(f"{self.name} has no handle() implemented")

    def say(self, message):
        line = f"[{self.division}/{self.name}] {message}"
        print(line)
        log(line)
