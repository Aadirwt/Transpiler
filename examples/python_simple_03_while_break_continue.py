i = 0
score = 0

while i < 8:
    i = i + 1
    if i == 2:
        continue
    elif i > 5:
        break
    else:
        score = score + i

print(score)
