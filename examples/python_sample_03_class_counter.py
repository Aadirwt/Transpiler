class Wallet:
    def __init__(self, start):
        self.amount = start

    def deposit(self, step):
        self.amount = self.amount + step
        return self.amount


w = Wallet(3)
print(w.deposit(4))
print(w.deposit(2))
