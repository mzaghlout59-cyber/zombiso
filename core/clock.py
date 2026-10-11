from config import settings


class SimClock:
    """The city's own time. One tick per cycle; a day is CYCLES_PER_DAY ticks.

    Tick 0 is before the first cycle. Ticks 1..CYCLES_PER_DAY are day 0, and so on.
    """

    def __init__(self, cycles_per_day=None):
        self.cycles_per_day = cycles_per_day or settings.CYCLES_PER_DAY
        self.tick = 0

    def advance(self):
        self.tick += 1

    @property
    def day(self):
        return max(self.tick - 1, 0) // self.cycles_per_day
