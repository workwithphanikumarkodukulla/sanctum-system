# calculator.py

def add(x, y):
    """Return the sum of two numbers."""
    return x + y


def subtract(x, y):
    """Return the difference of two numbers."""
    return x - y


def multiply(x, y):
    """Return the product of two numbers."""
    return x * y


def divide(x, y):
    """Return the quotient of two numbers."""
    if y == 0:
        raise ZeroDivisionError("Cannot divide by zero.")
    return x / y