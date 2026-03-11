def sort_numbers(nums):
    return sorted(nums)


def filter_positives(nums):
    return [n for n in nums if n > 0]


def find_duplicates(lst):
    seen: set = set()
    dupes: set = set()
    for x in lst:
        if x in seen:
            dupes.add(x)
        seen.add(x)
    return sorted(dupes)
