import os
import json
import sys

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)

import ai_engine

# Paths to generated test images
IMAGES = {
    "Pothole": r"C:\Users\HP\.gemini\antigravity\brain\5fc77256-e5d8-4216-acb5-370b84063367\pothole_test_1778586620621.png",
    "Water Leakage": r"C:\Users\HP\.gemini\antigravity\brain\5fc77256-e5d8-4216-acb5-370b84063367\water_leakage_test_1778586816705.png",
    "Garbage": r"C:\Users\HP\.gemini\antigravity\brain\5fc77256-e5d8-4216-acb5-370b84063367\garbage_test_1778586838745.png",
    "Drainage": r"C:\Users\HP\.gemini\antigravity\brain\5fc77256-e5d8-4216-acb5-370b84063367\drainage_test_1778587057104.png"
}

def run_tests():
    print("=" * 80)
    print("STARTING MULTIMODAL AI ANALYSIS VERIFICATION")
    print("=" * 80)
    
    results = {}
    
    for issue_type, img_path in IMAGES.items():
        print(f"\n--- Testing: {issue_type} ---")
        if not os.path.exists(img_path):
            print(f"ERROR: Image not found at {img_path}")
            continue
            
        try:
            # Test with image only (no text) to force true vision analysis
            print(f"Sending image for analysis: {os.path.basename(img_path)}")
            res = ai_engine.validate_and_summarize_grievance(text="", local_image_path=img_path)
            
            print(f"SUCCESS: Analysis received for {issue_type}")
            print(f"Title     : {res.get('title')}")
            print(f"Dept      : {res.get('department')}")
            print(f"Severity  : {res.get('severity')}")
            print(f"Sentiment : {res.get('sentiment')}")
            print(f"Summary   : {res.get('summary')[:100]}...")
            
            results[issue_type] = res
            
            print("\nWaiting 20 seconds before next test to avoid 503/Rate limits...")
            import time
            time.sleep(20)
        except Exception as e:
            print(f"FAILED: {issue_type} analysis failed with error: {e}")
            
    print("\n" + "=" * 80)
    print("FINAL VERIFICATION SUMMARY")
    print("=" * 80)
    
    for it, r in results.items():
        print(f"[{it}] Title: {r.get('title')} | Dept: {r.get('department')} | Sev: {r.get('severity')}")
        
    # Save results to a file for review
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to test_results.json")

if __name__ == "__main__":
    run_tests()
