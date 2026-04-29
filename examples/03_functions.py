def square(x: int) -> int:
    return x * x


def add(a: int, b: int) -> int:
    return a + b


value = add(square(3), 4)
print(value)
