class Counter:
    def __init__(self, start: int):
        self.value = start

    def bump(self, steps: int) -> int:
        total = self.value
        for i in range(0, steps, 1):
            total = total + 1
        self.value = total
        return self.value


c = Counter(2)
print(c.bump(3))
