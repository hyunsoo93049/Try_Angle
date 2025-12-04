#!/usr/bin/env python3
"""
Framing Analysis Summary - English Output
"""

import sys
import os
import warnings

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
    """Cafe photos framing analysis summary"""

    print("\n" + "="*70)
    print(" " * 10 + "FRAMING ANALYSIS: cafe4 vs cafe3")
    print("="*70)

    # Initialize quietly
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from compare_final_improved_v5_debug import SmartFeedbackV5Debug
        comparer = SmartFeedbackV5Debug()

        # Run analysis
        result = comparer.analyze_with_gates(
            "data/sample_images/cafe4.jpg",  # Current (table-heavy)
            "data/sample_images/cafe3.jpg"   # Reference (person-focused)
        )

    # Extract results
    if 'gates_result' in result and 'framing' in result['gates_result']:
        framing = result['gates_result']['framing']

        if 'details' in framing:
            details = framing['details']

            print("\n" + "-"*70)
            print(" " * 25 + "ANALYSIS RESULTS")
            print("-"*70)

            # Shot type
            shot = details['shot_type']
            print(f"\n[1] SHOT TYPE")
            print(f"    cafe4: {shot['current']['type']}")
            print(f"    cafe3: {shot['reference']['type']}")
            print(f"    Same category: {shot['same_category']}")
            print(f"    Score: {shot['score']}/100")

            # Subject ratio
            subject = details['subject_ratio']
            print(f"\n[2] SUBJECT RATIO (Person area / Total area)")
            print(f"    cafe4: {subject['current_ratio']*100:.1f}% (table-focused)")
            print(f"    cafe3: {subject['reference_ratio']*100:.1f}% (person-focused)")
            diff = abs(subject['reference_ratio'] - subject['current_ratio']) * 100
            print(f"    Difference: {diff:.1f}% points")
            print(f"    Score: {subject['score']}/100")

            # Bottom space (table)
            bottom = details['bottom_space']
            print(f"\n[3] BOTTOM SPACE RATIO (Table area)")
            print(f"    cafe4: {bottom['current_ratio']*100:.1f}% (more table visible)")
            print(f"    cafe3: {bottom['reference_ratio']*100:.1f}% (minimal table)")
            table_diff = abs(bottom['current_ratio'] - bottom['reference_ratio']) * 100
            print(f"    Difference: {table_diff:.1f}% points")
            print(f"    Score: {bottom['score']}/100")

            # Overall score
            print(f"\n[4] OVERALL FRAMING SCORE: {details['overall_score']:.0f}/100")
            print(f"    Weights: Shot(30%) + Subject(40%) + Bottom(30%)")

            # Key findings
            print("\n" + "-"*70)
            print(" " * 25 + "KEY FINDINGS")
            print("-"*70)

            print(f"\n1. Both photos are {shot['current']['type']} (same shot category)")
            print(f"2. cafe4 shows {diff:.0f}% less person area than cafe3")
            print(f"3. cafe4 shows {table_diff:.0f}% more table/bottom space than cafe3")
            print(f"4. Main issue: Different framing emphasis")
            print(f"   - cafe4: Table/environment focused")
            print(f"   - cafe3: Person focused")

            # Feedback
            feedback = details['feedback']
            if feedback['actions']:
                print("\n" + "-"*70)
                print(" " * 20 + "RECOMMENDED ADJUSTMENTS")
                print("-"*70)
                for i, action in enumerate(feedback['actions'][:3], 1):
                    # Translate key Korean feedback to English
                    if "closer" in action or "가까이" in action:
                        print(f"  {i}. Move closer to subject or zoom in")
                    elif "farther" in action or "멀어" in action:
                        print(f"  {i}. Move farther from subject or zoom out")
                    elif "테이블" in action or "하단" in action:
                        if "줄" in action or "최소" in action:
                            print(f"  {i}. Reduce table/bottom space - raise camera angle")
                        else:
                            print(f"  {i}. Include more table/bottom space")
                    elif "비중" in action:
                        print(f"  {i}. Adjust subject size to ~{subject['reference_ratio']*100:.0f}% of frame")
                    else:
                        # Keep original if can't translate
                        print(f"  {i}. {action}")

    # Overall system result
    if 'overall_score' in result:
        print("\n" + "="*70)
        print(f"FINAL SIMILARITY SCORE: {result['overall_score']:.1f}/100")
        print("="*70 + "\n")

if __name__ == "__main__":
    main()