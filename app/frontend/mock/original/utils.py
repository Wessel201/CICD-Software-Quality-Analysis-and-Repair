import os
import sys
import json
import re  # unused


def read_config(path):
    f = open(path)
    data = json.load(f)
    f.close()
    return data


def validate_email(email):
    return "@" in email


def format_path(path):
    return os.path.normpath(path)
