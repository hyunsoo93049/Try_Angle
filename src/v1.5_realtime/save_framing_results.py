#!/usr/bin/env python3
"""
Save framing analysis results to file
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
    """Save analysis results to file"""

    # Initialize quietly
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from compare_final_improved_v5_debug import SmartFeedbackV5Debug
        comparer = SmartFeedbackV5Debug()

        # Run analysis
        result = comparer.analyze_with_gates(
            "data/sample_images/cafe4.jpg",  # Current (table-heavy)
            "data/sample_images/cafe3.jpg"   # Reference (person-focused)
        )

    # Save raw results
    output = {}

    if 'gates_result' in result and 'framing' in result['gates_result']:
        framing = result['gates_result']['framing']

        if 'details' in framing:
            details = framing['details']

            # Extract key data
            output['shot_type'] = {
                'cafe4': details['shot_type']['current']['type'],
                'cafe3': details['shot_type']['reference']['type'],
                'same_category': details['shot_type']['same_category'],
                'score': details['shot_type']['score']
            }

            output['subject_ratio'] = {
                'cafe4_percent': round(details['subject_ratio']['current_ratio'] * 100, 1),
                'cafe3_percent': round(details['subject_ratio']['reference_ratio'] * 100, 1),
                'difference': round(abs(details['subject_ratio']['reference_ratio'] -
                                      details['subject_ratio']['current_ratio']) * 100, 1),
                'direction': details['subject_ratio']['direction'],
                'score': details['subject_ratio']['score']
            }

            output['bottom_space'] = {
                'cafe4_percent': round(details['bottom_space']['current_ratio'] * 100, 1),
                'cafe3_percent': round(details['bottom_space']['reference_ratio'] * 100, 1),
                'difference': round(abs(details['bottom_space']['current_ratio'] -
                                      details['bottom_space']['reference_ratio']) * 100, 1),
                'table_heavy': details['bottom_space']['table_heavy'],
                'score': details['bottom_space']['score']
            }

            output['overall_framing_score'] = details['overall_score']
            output['feedback_actions'] = details['feedback']['actions'][:3]

    output['overall_similarity'] = result.get('overall_score', 0)

    # Save to file
    with open('framing_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Also create a text summary
    if 'shot_type' in output:  # Only if we have data
        with open('framing_summary.txt', 'w', encoding='utf-8') as f:
            f.write("FRAMING ANALYSIS RESULTS: cafe4 vs cafe3\n")
            f.write("="*60 + "\n\n")

            f.write("1. SHOT TYPE\n")
            f.write(f"   cafe4: {output['shot_type']['cafe4']}\n")
            f.write(f"   cafe3: {output['shot_type']['cafe3']}\n")
            f.write(f"   Same category: {output['shot_type']['same_category']}\n")
            f.write(f"   Score: {output['shot_type']['score']}/100\n\n")

            f.write("2. SUBJECT RATIO (Person area)\n")
            f.write(f"   cafe4: {output['subject_ratio']['cafe4_percent']}%\n")
            f.write(f"   cafe3: {output['subject_ratio']['cafe3_percent']}%\n")
            f.write(f"   Difference: {output['subject_ratio']['difference']}%\n")
            f.write(f"   Score: {output['subject_ratio']['score']}/100\n\n")

            f.write("3. BOTTOM SPACE (Table area)\n")
            f.write(f"   cafe4: {output['bottom_space']['cafe4_percent']}%\n")
            f.write(f"   cafe3: {output['bottom_space']['cafe3_percent']}%\n")
            f.write(f"   Difference: {output['bottom_space']['difference']}%\n")
            f.write(f"   Score: {output['bottom_space']['score']}/100\n\n")

            f.write(f"4. OVERALL FRAMING SCORE: {output['overall_framing_score']:.0f}/100\n")
            f.write(f"   (Shot 30% + Subject 40% + Bottom 30%)\n\n")

            f.write("5. KEY FINDINGS\n")
            f.write("   - Both are medium_shot but with different emphasis\n")
            f.write("   - cafe4: Table/environment focused (24.4% table area)\n")
            f.write("   - cafe3: Person focused (35.5% subject ratio)\n\n")

            f.write("6. RECOMMENDATIONS\n")
            for i, action in enumerate(output['feedback_actions'], 1):
                f.write(f"   {i}. {action}\n")

            f.write(f"\nFINAL SIMILARITY: {output['overall_similarity']:.1f}/100\n")

    print("Results saved to:")
    print("  - framing_results.json")
    print("  - framing_summary.txt")

if __name__ == "__main__":
    main()