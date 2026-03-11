import os
import re
from dotenv import load_dotenv

load_dotenv()

class Repairman:
    """
    Handles code repair by applying fixes provided by an external AI.
    """
    def __init__(self):
        pass

    def isolate_snippet(self, file_path, line_number, context_lines=10):
        """Extracts a snippet of code around a specific line."""
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, "r") as f:
            lines = f.readlines()
        
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        
        snippet = "".join(lines[start:end])
        return {
            "snippet": snippet,
            "start_line": start + 1,
            "end_line": end
        }

    def apply_fix(self, file_path, start_line, end_line, new_code):
        """Replaces the old snippet with the repaired code."""
        with open(file_path, "r") as f:
            lines = f.readlines()
        
        lines[start_line-1 : end_line] = [new_code + "\n"]
        
        with open(file_path, "w") as f:
            f.writelines(lines)
        print(f"Applied fix to {file_path}")
