def fibonacci(n):
    """Generate the first n numbers in the Fibonacci series."""
    if n <= 0:
        return []
    if n == 1:
        return [0]

    series = [0, 1]
    while len(series) < n:
        series.append(series[-1] + series[-2])
    return series


def main():
    n = 10
    print(f"Fibonacci series up to {n} terms:")
    print(fibonacci(n))


if __name__ == "__main__":
    main()
