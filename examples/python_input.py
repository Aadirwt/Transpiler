def sum_to(n):
    total = 0
    for i in range(0, n, 1):
        total = total + i
    return total

x = sum_to(6)
if x > 10:
    print(x)
else:
    print(0)
