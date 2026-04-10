def scan(limit):
    current = 0
    total = 0
    while current < limit:
        current = current + 1
        if current == 2:
            continue
        elif current > 5:
            break
        else:
            total = total + current
    return total


result = scan(8)
if result != 0:
    print(result)
else:
    print(99)
