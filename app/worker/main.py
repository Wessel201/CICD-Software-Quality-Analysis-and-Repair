import os
import argparse
from analyzer import Analyzer
from repairman import Repairman

def run_worker(repo_path):
    print(f"Starting analysis on {repo_path}...")
    
    analyzer = Analyzer(repo_path)
    repairman = Repairman()
    
    # 1. Run analysis
    results = analyzer.run_all()
    
    # 2. Process findings (simplified for demonstration)
    # In a real scenario, we'd iterate through all findings.
    # Here we'll look for Bandit security issues first.
    security_findings = results.get("bandit", {}).get("results", [])
    
    for issue in security_findings:
        file_path = issue.get("filename")
        line_number = issue.get("line_number")
        issue_text = issue.get("issue_text")
        
        print(f"Found security issue: {issue_text} in {file_path}:{line_number}")
        
        # 3. Isolate snippet
        # Handle pathing: bandit might give relative or absolute paths
        target_file = os.path.join(repo_path, file_path) if not os.path.isabs(file_path) else file_path
        
        snippet_data = repairman.isolate_snippet(target_file, line_number)
        if snippet_data:
            print("Requesting repair from LLM...")
            # 4. Repair
            fixed_code = repairman.get_repair_suggestion(snippet_data["snippet"], issue_text)
            
            # 5. Apply fix
            repairman.apply_fix(target_file, snippet_data["start_line"], snippet_data["end_line"], fixed_code)
            
            # 6. Verification
            print("Verifying fix...")
            new_results = analyzer.run_bandit() # Re-run specific tool
            still_vulnerable = any(
                i.get("line_number") == line_number and i.get("filename") == file_path 
                for i in new_results.get("results", [])
            )
            
            if not still_vulnerable:
                print(f"SUCCESS: Issue {issue_text} fixed in {file_path}")
                # TODO: Implement Git branching and pushing here
                # Example: git checkout -b fix/security-issue && git add . && git commit -m "Fix" && git push
                print("TODO: Push changes to a new branch (Git integration needed)")
            else:
                print(f"FAILED: Issue {issue_text} still present after repair.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QC Worker for Analysis and Repair")
    parser.add_argument("--repo", type=str, default=".", help="Path to the repository to analyze")
    args = parser.parse_args()
    
    run_worker(args.repo)
