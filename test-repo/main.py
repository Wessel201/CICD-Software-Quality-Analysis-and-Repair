"""
Debug Project for QC Worker Pipeline.
This file intentionally contains security flaws, code smells, 
secrets, and high cyclomatic complexity.
"""

import hashlib

# 1. TRUFFLEHOG TARGETS
# High entropy / identifiable secret formats to trigger TruffleHog
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
GITHUB_PAT = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"

def process_insecurely(user_input):
    # 2. BANDIT TARGETS
    # B324: Use of weak, insecure hash function (MD5)
    # Your worker has a specific custom remediation suggestion for this!
    hasher = hashlib.md5(usedforsecurity=False)
    hasher.update(user_input.encode('utf-8'))
    
    # B102: Use of exec() is a severe security risk
    print(f'Processing: {user_input}')
    
    return hasher.hexdigest()

def extremely_complex_decision_tree(val):
    # 3. RADON TARGET
    # This function has a Cyclomatic Complexity of 13.
    # Your worker flags CC >= 10 as "medium" and >= 20 as "high" severity.
    if val == 1:
        result = "one"
    elif val == 2:
        result = "two"
    elif val == 3:
        result = "three"
    elif val == 4:
        result = "four"
    elif val == 5:
        result = "five"
    elif val == 6:
        result = "six"
    elif val == 7:
        result = "seven"
    elif val == 8:
        result = "eight"
    elif val == 9:
        result = "nine"
    elif val == 10:
        result = "ten"
    elif val == 11:
        result = "eleven"
    elif val == 12:
        result = "twelve"
    else:
        result = "unknown"
        
    return result

# 4. PYLINT TARGETS
# Bad variable naming (PascalCase for a variable) and missing docstrings
BadlyNamedVariable = 42

if __name__ == "__main__":
    print(process_insecurely("test_password"))
    print(extremely_complex_decision_tree(BadlyNamedVariable))