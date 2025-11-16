# ============================================================
# 🎯 TryAngle - Main Feedback System
# 레퍼런스 vs 사용자 이미지 비교 및 피드백 제공
# ============================================================

import os
import sys
from pathlib import Path

# 경로 설정
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR
while PROJECT_ROOT != PROJECT_ROOT.parent and not ((PROJECT_ROOT / "data").exists() and (PROJECT_ROOT / "src").exists()):
    PROJECT_ROOT = PROJECT_ROOT.parent

VERSION3_DIR = PROJECT_ROOT / "src" / "Multi" / "version3"
ANALYSIS_DIR = VERSION3_DIR / "analysis"

if str(VERSION3_DIR) not in sys.path:
    sys.path.append(str(VERSION3_DIR))
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.append(str(ANALYSIS_DIR))

from analysis.image_comparator import ImageComparator


def main():
    """
    메인 함수
    """
    
    # ==========================================
    # 이미지 경로 설정
    # ==========================================
    #reference_path = PROJECT_ROOT / "data" / "clustered_images" / "cluster_5" / "IMG_0561.JPG"
    reference_path = PROJECT_ROOT / "data" / "test_images" / "test3.jpg"
    user_path = PROJECT_ROOT / "data" / "test_images" / "test4.jpg"
    
    # 경로 확인
    if not reference_path.exists():
        print(f"❌ 레퍼런스 이미지를 찾을 수 없습니다: {reference_path}")
        return
    
    
    if not user_path.exists():
        print(f"❌ 사용자 이미지를 찾을 수 없습니다: {user_path}")
        return
    
    print("\n" + "🎯 TryAngle - 촬영 피드백 시스템".center(60, "="))
    print(f"레퍼런스: {reference_path.name}")
    print(f"사용자  : {user_path.name}")
    
    try:
        # ==========================================
        # 이미지 비교
        # ==========================================
        comparator = ImageComparator(str(reference_path), str(user_path))
        
        # ==========================================
        # 우선순위 피드백 받기
        # ==========================================
        feedback = comparator.get_prioritized_feedback()
        
        # ==========================================
        # 결과 출력
        # ==========================================
        print("\n" + "="*60)
        print("📋 촬영 가이드".center(60))
        print("="*60)
        
        # 정보성 메시지 (클러스터)
        info_messages = [fb for fb in feedback if fb["priority"] == 0]
        actionable_messages = [fb for fb in feedback if fb["priority"] > 0]
        
        if info_messages:
            print("\n📊 스타일 정보:")
            for fb in info_messages:
                print(f"   {fb['message']}")
                print(f"   └ {fb['detail']}")
        
        if actionable_messages:
            print("\n🎬 촬영 조정 사항:")
            for i, fb in enumerate(actionable_messages, 1):
                print(f"\n   {i}. [{fb['category'].upper()}] {fb['message']}")
                print(f"      └ {fb['detail']}")
        else:
            print("\n✅ 완벽합니다! 조정 사항이 없습니다.")
        
        print("\n" + "="*60)
        
        # ==========================================
        # 상세 비교 정보 (옵션)
        # ==========================================
        comparison = comparator.compare()
        
        print("\n" + "="*60)
        print("📊 상세 비교 정보".center(60))
        print("="*60)
        
        # 클러스터
        cluster = comparison["cluster_comparison"]
        print(f"\n🎯 Cluster:")
        print(f"   레퍼런스: {cluster['reference_cluster']} - {cluster['reference_label']}")
        print(f"   사용자  : {cluster['user_cluster']} - {cluster['user_label']}")
        print(f"   임베딩 거리: {cluster['embedding_distance']:.4f}")
        
        # Depth
        depth = comparison["depth_comparison"]
        print(f"\n📏 Depth:")
        print(f"   레퍼런스: {depth['ref_depth']:.1f}")
        print(f"   사용자  : {depth['user_depth']:.1f}")
        print(f"   비율    : {depth['ratio']:.2f}")
        
        # 밝기
        brightness = comparison["brightness_comparison"]
        print(f"\n💡 Brightness:")
        print(f"   레퍼런스: {brightness['ref_brightness']:.1f}")
        print(f"   사용자  : {brightness['user_brightness']:.1f}")
        print(f"   차이    : {brightness['difference']:.1f}")
        print(f"   EV 조정 : {brightness['ev_adjustment']:.2f}")
        
        # 색감
        color = comparison["color_comparison"]
        print(f"\n🎨 Color:")
        print(f"   레퍼런스: 채도={color['ref_saturation']:.2f}, 색온도={color['ref_temperature']}")
        print(f"   사용자  : 채도={color['user_saturation']:.2f}, 색온도={color['user_temperature']}")
        
        # 구도
        comp = comparison["composition_comparison"]
        print(f"\n📐 Composition:")
        print(f"   레퍼런스 기울기: {comp['ref_tilt']:.1f}°")
        print(f"   사용자 기울기  : {comp['user_tilt']:.1f}°")
        print(f"   차이          : {comp['tilt_diff']:.1f}°")

        # 포즈
        pose = comparison["pose_comparison"]
        if pose["available"]:
            print(f"\n🤸 Pose:")
            print(f"   유사도: {pose.get('similarity', 0.0):.2%}")
            if pose["angle_differences"]:
                print(f"   각도 차이: {len(pose['angle_differences'])}개 관절")
            if pose["position_differences"]:
                print(f"   위치 차이: {len(pose['position_differences'])}개 키포인트")
        else:
            print(f"\n🤸 Pose: 사용 불가")

        # EXIF (카메라 설정)
        exif = comparison["exif_comparison"]
        if exif["available"]:
            print(f"\n📷 Camera Settings:")
            ref_settings = exif.get("ref_settings", {})
            user_settings = exif.get("user_settings", {})

            if "iso" in ref_settings:
                print(f"   ISO: 레퍼런스={ref_settings.get('iso')}, 현재={user_settings.get('iso')}")
            if "f_number" in ref_settings:
                print(f"   조리개: 레퍼런스=f/{ref_settings.get('f_number'):.1f}, 현재=f/{user_settings.get('f_number'):.1f}")
            if "shutter_speed_display" in ref_settings:
                print(f"   셔터속도: 레퍼런스={ref_settings.get('shutter_speed_display')}, 현재={user_settings.get('shutter_speed_display')}")
            if "focal_length" in ref_settings:
                print(f"   초점거리: 레퍼런스={ref_settings.get('focal_length'):.0f}mm, 현재={user_settings.get('focal_length'):.0f}mm")

            if exif.get("has_differences"):
                print(f"   ⚠️ 카메라 설정 조정 필요")
        else:
            print(f"\n📷 Camera Settings: EXIF 데이터 없음")

        # Quality (노이즈, 블러, 선명도, 대비)
        quality = comparison["quality_comparison"]
        if quality["available"]:
            print(f"\n🔍 Quality:")
            if quality["feedback"]:
                print(f"   피드백 {len(quality['feedback'])}개:")
                for i, fb in enumerate(quality["feedback"], 1):
                    print(f"   {i}. [{fb['category'].upper()}] {fb['message']}")
                    print(f"      조정: {fb['adjustment']}")
                    if fb.get('adjustment_numeric'):
                        print(f"      수치: {fb['adjustment_numeric']}")
            else:
                print(f"   ✅ 품질이 적절합니다")
        else:
            print(f"\n🔍 Quality: 분석 불가")

        # Lighting (조명 방향, 역광, HDR)
        lighting = comparison["lighting_comparison"]
        if lighting.get("available", False):
            print(f"\n💡 Lighting:")
            if lighting.get("has_issues", False) and lighting.get("feedback"):
                print(f"   피드백 {len(lighting['feedback'])}개:")
                for i, fb in enumerate(lighting["feedback"], 1):
                    print(f"   {i}. [{fb['category'].upper()}] {fb['message']}")
                    print(f"      조정: {fb['adjustment']}")
                    if fb.get('adjustment_numeric'):
                        print(f"      수치: {fb['adjustment_numeric']}")
            else:
                print(f"   ✅ 조명이 적절합니다")
        else:
            print(f"\n💡 Lighting: 분석 불가")

        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
