class Measure:
    def __init__(self, base):
        self.base = base

    def scale(self, times):
        total = self.base
        for i in range(0, times, 1):
            total = total + 1.5
        self.base = total
        return self.base

    def tag(n):
        return n + 10


m = Measure(2.0)
value = m.scale(2)
bonus = Measure.tag(5)
print(value)
print(bonus)
