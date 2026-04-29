total = 0

for i in range(0, 8, 1):
    if i == 3:
        continue
    elif i > 5:
        break
    else:
        total = total + i

print(total)
