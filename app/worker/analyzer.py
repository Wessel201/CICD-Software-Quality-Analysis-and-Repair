import subprocess
import json
import logging
import time


logger = logging.getLogger(__name__)

class Analyzer:
    """
    Orchestrates multiple static analysis tools.
    """
    def __init__(self, target_path):
        self.target_path = target_path

    def run_bandit(self):
        """Runs Bandit for security analysis."""
        logger.info("Running Bandit", extra={"event": "tool_start"})
        started_at = time.time()
        try:
            result = subprocess.run(
                ["bandit", "-r", self.target_path, "-f", "json"],
                capture_output=True, text=True
            )
            payload = json.loads(result.stdout)
            duration_ms = int((time.time() - started_at) * 1000)
            logger.info("Bandit complete", extra={"event": "tool_complete", "duration_ms": duration_ms})
            return payload
        except Exception as e:
            logger.exception("Bandit failed", extra={"event": "tool_failed"})
            return {"error": str(e)}

    def run_pylint(self):
        """Runs Pylint for code quality."""
        logger.info("Running Pylint", extra={"event": "tool_start"})
        started_at = time.time()
        try:
            # Pylint doesn't output pure JSON easily without plugins, 
            # we'll use a template for semi-structured output or parse short format.
            result = subprocess.run(
                ["pylint", self.target_path, "--output-format=json"],
                capture_output=True, text=True
            )
            payload = json.loads(result.stdout)
            duration_ms = int((time.time() - started_at) * 1000)
            logger.info("Pylint complete", extra={"event": "tool_complete", "duration_ms": duration_ms})
            return payload
        except Exception as e:
            logger.exception("Pylint failed", extra={"event": "tool_failed"})
            return {"error": str(e)}

    def run_radon(self):
        """Runs Radon for complexity analysis."""
        logger.info("Running Radon", extra={"event": "tool_start"})
        started_at = time.time()
        try:
            result = subprocess.run(
                ["radon", "cc", self.target_path, "-j"],
                capture_output=True, text=True
            )
            payload = json.loads(result.stdout)
            duration_ms = int((time.time() - started_at) * 1000)
            logger.info("Radon complete", extra={"event": "tool_complete", "duration_ms": duration_ms})
            return payload
        except Exception as e:
            logger.exception("Radon failed", extra={"event": "tool_failed"})
            return {"error": str(e)}

    def run_trufflehog(self):
        """Runs TruffleHog for secret scanning."""
        logger.info("Running TruffleHog", extra={"event": "tool_start"})
        started_at = time.time()
        try:
            # Note: TruffleHog v3+ uses different CLI. Assuming v3 here.
            # Using filesystem scan.
            result = subprocess.run(
                ["trufflehog", "filesystem", self.target_path, "--json"],
                capture_output=True, text=True
            )
            # TruffleHog outputs multiple JSON objects, one per line usually
            findings = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            duration_ms = int((time.time() - started_at) * 1000)
            logger.info("TruffleHog complete", extra={"event": "tool_complete", "duration_ms": duration_ms})
            return findings
        except Exception as e:
            logger.exception("TruffleHog failed", extra={"event": "tool_failed"})
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
