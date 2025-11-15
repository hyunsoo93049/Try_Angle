# Debug pose comparison
import sys
sys.path.append(r"C:\try_angle\src\Multi\version3")

from analysis.pose_analyzer import PoseAnalyzer, compare_poses
import json

print("="*60)
print("Pose Comparison Debug")
print("="*60)

# Test images
ref_path = r"C:\try_angle\data\test_images\test2.jpg"
user_path = r"C:\try_angle\data\test_images\test1.jpg"

# Analyze poses
analyzer = PoseAnalyzer()

print("\n[1] Analyzing Reference Image (test2.jpg)")
ref_pose = analyzer.analyze(ref_path)
print(f"    Scenario: {ref_pose['scenario']}")
print(f"    Confidence: {ref_pose['confidence']:.2f}")
print(f"    YOLO keypoints: {len(ref_pose['yolo_keypoints'])}")

print("\n[2] Analyzing User Image (test1.jpg)")
user_pose = analyzer.analyze(user_path)
print(f"    Scenario: {user_pose['scenario']}")
print(f"    Confidence: {user_pose['confidence']:.2f}")
print(f"    YOLO keypoints: {len(user_pose['yolo_keypoints'])}")

print("\n[3] Comparing Poses...")
print(f"    Same scenario? {ref_pose['scenario'] == user_pose['scenario']}")

# Check keypoint confidences
print("\n[4] Reference Keypoint Confidences:")
for kp in ref_pose['yolo_keypoints'][:5]:
    print(f"    {kp['name']}: {kp['confidence']:.2f}")

print("\n[5] User Keypoint Confidences:")
for kp in user_pose['yolo_keypoints'][:5]:
    print(f"    {kp['name']}: {kp['confidence']:.2f}")

# Compare
comparison = compare_poses(ref_pose, user_pose)

print("\n[6] Comparison Result:")
print(f"    Similarity: {comparison['similarity']:.2%}")
print(f"    Angle differences: {len(comparison.get('angle_differences', {}))}")
print(f"    Position differences: {len(comparison.get('position_differences', {}))}")

if 'angle_differences' in comparison:
    print("\n[7] Angle Differences:")
    for joint, diff in comparison['angle_differences'].items():
        print(f"    {joint}: {diff:.1f}°")

if 'position_differences' in comparison:
    print("\n[8] Position Differences:")
    for point, diff in comparison['position_differences'].items():
        print(f"    {point}: {diff:.3f}")

print("\n[9] Feedback:")
for i, fb in enumerate(comparison['feedback'], 1):
    print(f"    {i}. {fb}")

# Debug merged keypoints
print("\n[10] Reference Merged Keypoints (base):")
ref_base = ref_pose['merged_keypoints']['base']
for name in ['left_shoulder', 'left_elbow', 'left_wrist', 'right_shoulder', 'right_elbow', 'right_wrist']:
    if name in ref_base:
        kp = ref_base[name]
        print(f"    {name}: x={kp['x']:.3f}, y={kp['y']:.3f}, conf={kp['confidence']:.2f}")

print("\n[11] User Merged Keypoints (base):")
user_base = user_pose['merged_keypoints']['base']
for name in ['left_shoulder', 'left_elbow', 'left_wrist', 'right_shoulder', 'right_elbow', 'right_wrist']:
    if name in user_base:
        kp = user_base[name]
        print(f"    {name}: x={kp['x']:.3f}, y={kp['y']:.3f}, conf={kp['confidence']:.2f}")

print("\n" + "="*60)
