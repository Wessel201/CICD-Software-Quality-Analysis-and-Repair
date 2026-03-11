import os
import sys
import json
import re


def read_config(path):
    with open(path) as f:
        data = json.load(f)
    return data


def validate_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def format_path(path):
    return os.path.normpath(path)
