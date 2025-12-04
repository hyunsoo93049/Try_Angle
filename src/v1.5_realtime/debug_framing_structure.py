#!/usr/bin/env python3
"""
Debug framing structure
"""

import sys
import os
import warnings
import json

# Suppress warnings
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Path setup
sys.path.insert(0, r'C:\try_angle\v1.5_ios\src\v1.5_realtime')
os.chdir(r'C:\try_angle')

# Redirect stdout
import io
from contextlib import redirect_stdout, redirect_stderr

def main():
    """Debug analysis structure"""

    # Initialize quietly
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from compare_final_improved_v5_debug import SmartFeedbackV5Debug
        comparer = SmartFeedbackV5Debug()

        # Run analysis
        result = comparer.analyze_with_gates(
            "data/sample_images/cafe4.jpg",
            "data/sample_images/cafe3.jpg"
        )

    # Debug: Print structure
    print("Result keys:", list(result.keys()))

    if 'all_gates' in result:
        print("Gates keys:", list(result['all_gates'].keys()))

        if 'framing' in result['all_gates']:
            framing = result['all_gates']['framing']
            print("Framing keys:", list(framing.keys()))

            # Check if it's the expected structure
            if 'details' in framing:
                print("Details found!")
                details = framing['details']
                print("Details keys:", list(details.keys()))

                # Try to extract data
                if 'shot_type' in details:
                    shot = details['shot_type']
                    print("\nShot type data:")
                    print(f"  Current: {shot.get('current', {}).get('type', 'N/A')}")
                    print(f"  Reference: {shot.get('reference', {}).get('type', 'N/A')}")

                if 'subject_ratio' in details:
                    subj = details['subject_ratio']
                    print("\nSubject ratio data:")
                    print(f"  Current: {subj.get('current_ratio', 0)*100:.1f}%")
                    print(f"  Reference: {subj.get('reference_ratio', 0)*100:.1f}%")

                if 'bottom_space' in details:
                    bottom = details['bottom_space']
                    print("\nBottom space data:")
                    print(f"  Current: {bottom.get('current_ratio', 0)*100:.1f}%")
                    print(f"  Reference: {bottom.get('reference_ratio', 0)*100:.1f}%")

                print(f"\nOverall framing score: {details.get('overall_score', 0):.0f}")
            else:
                print("No 'details' key in framing!")
                print("Framing structure:", json.dumps(framing, indent=2, ensure_ascii=False)[:500])
        else:
            print("No 'framing' in all_gates")
    else:
        print("No 'all_gates' in result")

if __name__ == "__main__":
    main()