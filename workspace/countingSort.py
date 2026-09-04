def counting_sort(arr):
    max_val = max(arr)
    count = [0] * (max_val + 1)

    for num in arr:
        count[num] += 1

    sorted_arr = []
    for i, cnt in enumerate(count):
        sorted_arr += [i] * cnt

    return sorted_arr

# Example usage:
arr = [4, 2, 2, 8, 3, 3, 1]
print("Original array:", arr)
print("Sorted array:", counting_sort(arr))