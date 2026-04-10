value = 1.5
steps = 0

for i in range(0, 4, 1):
    value = value + 1.0
    steps = steps + 1

if value > 3.0:
    if steps == 4:
        print(value)
    else:
        print(steps)
else:
    print(0)
