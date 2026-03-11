def sort_numbers(nums):
    # Manual bubble sort
    for i in range(len(nums)):
        for j in range(len(nums) - 1):
            if nums[j] > nums[j + 1]:
                temp = nums[j]
                nums[j] = nums[j + 1]
                nums[j + 1] = temp
    return nums


def filter_positives(nums):
    result = []
    for n in nums:
        if n > 0:
            result.append(n)
    return result


def find_duplicates(lst):
    seen = []
    dupes = []
    for x in lst:
        if x in seen:
            if x not in dupes:
                dupes.append(x)
        seen.append(x)
    return dupes
