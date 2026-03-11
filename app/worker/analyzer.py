import subprocess
import json

class Analyzer:
    """
    Orchestrates multiple static analysis tools.
    """
    def __init__(self, target_path):
        self.target_path = target_path

    def run_bandit(self):
        """Runs Bandit for security analysis."""
        print(f"Running Bandit on {self.target_path}...")
        try:
            result = subprocess.run(
                ["bandit", "-r", self.target_path, "-f", "json"],
                capture_output=True, text=True
            )
            return json.loads(result.stdout)
        except Exception as e:
            return {"error": str(e)}

    def run_pylint(self):
        """Runs Pylint for code quality."""
        print(f"Running Pylint on {self.target_path}...")
        try:
            # Pylint doesn't output pure JSON easily without plugins, 
            # we'll use a template for semi-structured output or parse short format.
            result = subprocess.run(
                ["pylint", self.target_path, "--output-format=json"],
                capture_output=True, text=True
            )
            return json.loads(result.stdout)
        except Exception as e:
            return {"error": str(e)}

    def run_radon(self):
        """Runs Radon for complexity analysis."""
        print(f"Running Radon on {self.target_path}...")
        try:
            result = subprocess.run(
                ["radon", "cc", self.target_path, "-j"],
                capture_output=True, text=True
            )
            return json.loads(result.stdout)
        except Exception as e:
            return {"error": str(e)}

    def run_trufflehog(self):
        """Runs TruffleHog for secret scanning."""
        print(f"Running TruffleHog on {self.target_path}...")
        try:
            # Note: TruffleHog v3+ uses different CLI. Assuming v3 here.
            # Using filesystem scan.
            result = subprocess.run(
                ["trufflehog", "filesystem", self.target_path, "--json"],
                capture_output=True, text=True
            )
            # TruffleHog outputs multiple JSON objects, one per line usually
            findings = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            return findings
        except Exception as e:
            return {"error": str(e)}

    def run_all(self):
        """Runs all tools and aggregates results."""
        return {
            "bandit": self.run_bandit(),
            "pylint": self.run_pylint(),
            "radon": self.run_radon(),
            "trufflehog": self.run_trufflehog()
        }

if __name__ == "__main__":
    # Test run
    analyzer = Analyzer(".")
    # results = analyzer.run_all()
    # print(json.dumps(results, indent=2))
