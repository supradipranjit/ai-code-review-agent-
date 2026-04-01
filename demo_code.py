# demo_code.py

# 🔴 SECURITY ISSUE
def login(user_input):
    # Unsafe eval (code injection)
    return eval(user_input)


# 🟡 PERFORMANCE ISSUE
def get_squares(nums):
    result = []
    for i in range(len(nums)):  # inefficient loop
        result.append(nums[i] * nums[i])
    return result


# 🔵 STYLE ISSUE
def add(a,b):  # bad spacing, no docstring
    return a+b
