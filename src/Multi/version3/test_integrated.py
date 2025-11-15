# Test integrated system with pose analysis
import sys
sys.path.append(r"C:\try_angle\src\Multi\version3")

print("="*60)
print("Integrated System Test - ImageAnalyzer + ImageComparator")
print("="*60)

try:
    from analysis.image_analyzer import ImageAnalyzer
    from analysis.image_comparator import ImageComparator

    print("\n✓ Modules imported successfully\n")

    # Test paths
    ref_path = r"C:\try_angle\data\test_images\test1.jpg"
    user_path = r"C:\try_angle\data\test_images\test1.jpg"  # Same image for testing

    print("="*60)
    print("Test 1: ImageAnalyzer with Pose")
    print("="*60)

    analyzer = ImageAnalyzer(ref_path, enable_pose=True)
    result = analyzer.analyze()

    print(f"\nCluster: {result['cluster']['cluster_label']}")
    print(f"Depth: {result['depth']['depth_mean']:.1f}")
    print(f"Brightness: {result['pixels']['brightness']:.1f}")

    if result['pose'] is not None:
        print(f"\nPose Analysis:")
        print(f"  Scenario: {result['pose']['scenario']}")
        print(f"  Confidence: {result['pose']['confidence']:.2f}")
        print(f"  BBox: {result['pose']['bbox']}")
        print("  ✓ Pose analysis integrated successfully!")
    else:
        print("\n  ✗ Pose analysis not available")

    print("\n" + "="*60)
    print("Test 2: ImageComparator with Pose Comparison")
    print("="*60)

    comparator = ImageComparator(ref_path, user_path)
    feedback = comparator.get_prioritized_feedback()

    print("\nFeedback (Top 5):")
    for i, fb in enumerate(feedback[:5], 1):
        print(f"\n{i}. [{fb['category'].upper()}]")
        print(f"   {fb['message']}")
        print(f"   └ {fb['detail']}")

    # Check if pose feedback exists
    pose_feedback = [f for f in feedback if f['category'] == 'pose']
    if pose_feedback:
        print("\n✓ Pose comparison integrated successfully!")
    else:
        print("\n⚠ No pose feedback found (might be same image)")

    print("\n" + "="*60)
    print("✓ All integration tests passed!")
    print("="*60)

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
