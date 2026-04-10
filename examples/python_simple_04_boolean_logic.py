a = True
b = False
count = 2

if a and not b:
    count = count + 3
else:
    count = 0

if count >= 5 or b:
    print(count)
else:
    print(9)
