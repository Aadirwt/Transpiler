class Counter:
    def __init__(self, start):
        self.value = start

    def bump(self, steps):
        total = self.value
        for i in range(0, steps, 1):
            if i == 2:
                continue
            elif i > 4:
                break
            else:
                total = total + 1
        self.value = total
        return self.value


c = Counter(1)
result = c.bump(7)
if result > 3:
    print(result)
else:
    print(0)
