def sum_until(limit):
    total = 0
    for i in range(0, limit, 1):
        total = total + i
    return total


value = sum_until(6)
if value >= 15:
    print(value)
else:
    print(0)
