from config import settings
from core.logger import log


class Agent:
    def __init__(self, name):
        self.name = name
        self.balance = settings.ACCOUNT_SIZE

    def report(self):
        print(f"Agent {self.name} has balance {self.balance}")

    def paper_trade(self, profit):
        self.balance = self.balance + profit
        msg = f"{self.name} made a paper trade of {profit}"
        print(msg)
        log(msg)
