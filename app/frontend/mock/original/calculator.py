def divide(a, b):
    return a / b


def calculate_average(numbers):
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)


class Calculator:
    def __init__(self):
        self.history = []

    def add(self, a, b):
        result = a + b
        self.history.append(result)
        return result

    def multiply(self, a, b):
        return a * b
