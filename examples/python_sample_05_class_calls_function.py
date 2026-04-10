def inc(x):
    return x + 1


class Lamp:
    def __init__(self, start):
        self.level = start

    def brighten(self, steps):
        total = self.level
        for i in range(0, steps, 1):
            total = inc(total)
        self.level = total
        return self.level


lamp = Lamp(1)
level = lamp.brighten(3)
ready = True
if ready and level > 2:
    print(level)
else:
    print(0)
