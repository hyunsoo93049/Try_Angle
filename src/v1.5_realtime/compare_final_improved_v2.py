#!/usr/bin/env python3
"""
TryAngle v1.5 - 개선된 이미지 비교 도구 v2
비판적 검토를 반영한 더 정확한 피드백 시스템
"""

import sys
import os
import time
import traceback
import math
from pathlib import Path
from typing import Optional, Tuple, Dict, List
import re

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 경로 추가
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "legacy"))
sys.path.append(str(Path(__file__).parent.parent / "v1.5_learning"))

# Legacy 시스템 임포트
from legacy.reference_comparison import (
    ReferenceComparison,
    ComparisonResult,
    ImageAnalysis
)


class ImprovedFeedbackV2:
    """개선된 피드백 생성기 v2"""

    def __init__(self):
        self.device_zoom_systems = {
            "iPhone": [0.5, 1.0, 2.0, 3.0, 5.0],
            "Galaxy": [0.6, 1.0, 3.0, 10.0],
            "generic": [0.5, 1.0, 2.0, 3.0, 5.0]
        }

    def convert_position_to_grid(self, x: float, y: float) -> Dict[str, any]:
        """좌표를 3분할 구도 기준으로 변환"""

        # 3x3 그리드 위치
        grid_x = min(int(x * 3) + 1, 3)  # 1, 2, 3
        grid_y = min(int(y * 3) + 1, 3)  # 1, 2, 3

        # 자연어 설명
        horizontal = "왼쪽" if x < 0.33 else "중앙" if x < 0.67 else "오른쪽"
        vertical = "상단" if y < 0.33 else "중간" if y < 0.67 else "하단"

        # 황금비 위치 확인 (대략 0.382, 0.618)
        is_golden_x = abs(x - 0.382) < 0.05 or abs(x - 0.618) < 0.05
        is_golden_y = abs(y - 0.382) < 0.05 or abs(y - 0.618) < 0.05

        return {
            "grid": (grid_x, grid_y),
            "description": f"{vertical} {horizontal}",
            "grid_description": f"3분할 {grid_x}-{grid_y}구역",
            "is_golden": is_golden_x or is_golden_y,
            "exact": (x, y)
        }

    def calculate_camera_movement(self, current_pos: Tuple[float, float],
                                 target_pos: Tuple[float, float]) -> Dict[str, any]:
        """정확한 카메라 이동 계산 (수직 이동 로직 수정)"""

        x_diff = target_pos[0] - current_pos[0]
        y_diff = target_pos[1] - current_pos[1]

        instructions = []

        # 수평 이동 (좌우)
        if abs(x_diff) > 0.02:  # 2% 이상 차이
            if x_diff > 0:
                # 피사체를 화면 오른쪽으로 = 카메라를 왼쪽으로
                camera_dir = "왼쪽"
                subject_dir = "오른쪽"
            else:
                camera_dir = "오른쪽"
                subject_dir = "왼쪽"

            percentage = abs(x_diff * 100)
            instructions.append({
                "type": "horizontal",
                "camera_movement": f"카메라를 {camera_dir}으로 {percentage:.0f}% 이동",
                "subject_result": f"피사체가 화면에서 {subject_dir}으로 이동",
                "alternative": f"또는 피사체에게 {camera_dir}으로 이동 요청"
            })

        # 수직 이동 (상하) - 수정된 로직
        if abs(y_diff) > 0.02:
            if y_diff > 0:
                # 피사체를 화면 아래로 (더 많이 보이게) = 카메라를 아래로 틸트
                camera_action = "아래로 틸트 (또는 뒤로 물러나기)"
                subject_result = "피사체가 더 많이 보임 (전신 방향)"
                alternative = "줌아웃 또는 카메라 위치를 낮추기"
            else:
                # 피사체를 화면 위로 (상체 위주) = 카메라를 위로 틸트
                camera_action = "위로 틸트 (또는 가까이 가기)"
                subject_result = "피사체 상체/얼굴 위주로 보임"
                alternative = "줌인 또는 카메라 위치를 높이기"

            percentage = abs(y_diff * 100)
            instructions.append({
                "type": "vertical",
                "camera_movement": f"카메라를 {camera_action}",
                "subject_result": subject_result,
                "alternative": alternative,
                "percentage": f"{percentage:.0f}%"
            })

        return {
            "needs_adjustment": len(instructions) > 0,
            "instructions": instructions,
            "distance": math.sqrt(x_diff**2 + y_diff**2)
        }

    def calculate_exact_zoom_ratio(self, current_comp: float, target_comp: float) -> float:
        """정확한 줌 배율 계산 (실용적 범위: 0.5x ~ 3x)

        스마트폰 카메라 실제 매핑:
        압축감 0.0 = 0.5x (13mm) - 초광각
        압축감 0.15 = 1.0x (24mm) - 표준
        압축감 0.35 = 2.0x (48mm) - 2배줌
        압축감 0.5 = 3.0x (72mm) - 3배줌 (실용 한계)
        """

        def compression_to_zoom(comp):
            """압축감을 줌 배율로 변환 (실용적 범위 제한)"""
            if comp <= 0.15:
                # 0.0~0.15: 0.5x~1.0x 구간
                return 0.5 + (comp / 0.15) * 0.5
            elif comp <= 0.35:
                # 0.15~0.35: 1.0x~2.0x 구간
                return 1.0 + ((comp - 0.15) / 0.20) * 1.0
            elif comp <= 0.5:
                # 0.35~0.5: 2.0x~3.0x 구간
                return 2.0 + ((comp - 0.35) / 0.15) * 1.0
            else:
                # 0.5 이상: 3x로 제한 (더 이상은 비실용적)
                # 실제로는 3x 이상이지만 3x로 표시
                theoretical_zoom = 3.0 + ((comp - 0.5) / 0.5) * 7.0
                return min(theoretical_zoom, 10.0)  # 이론값 계산용

        # 줌 배율 계산
        current_zoom = compression_to_zoom(current_comp)
        target_zoom = compression_to_zoom(target_comp)

        # 실용적 줌 범위 (0.5x ~ 3x)
        practical_current = min(current_zoom, 3.0)
        practical_target = min(target_zoom, 3.0)

        # 초점거리 계산 (24mm = 1x 기준)
        current_focal = round(practical_current * 24)
        target_focal = round(practical_target * 24)

        # 필요한 줌 조정 비율
        zoom_ratio = practical_target / practical_current if practical_current > 0 else 1

        # 3x를 초과하는 경우 거리 조정 필요
        needs_distance_adjustment = target_zoom > 3.0

        return {
            "current_focal_mm": current_focal,
            "target_focal_mm": target_focal,
            "current_zoom": round(practical_current, 1),
            "target_zoom": round(practical_target, 1),
            "theoretical_target_zoom": round(target_zoom, 1),  # 이론적 목표값
            "zoom_ratio": round(zoom_ratio, 1),
            "zoom_direction": "줌 인" if zoom_ratio > 1 else "줌 아웃",
            "needs_distance_adjustment": needs_distance_adjustment,
            "max_zoom_reached": practical_target >= 3.0
        }

    def analyze_compression_accurately(self, compression: float,
                                      device_type: str = "generic") -> Dict[str, any]:
        """압축감을 정확히 분석 (0.5x = 13mm 최소 기준)"""

        # compression_to_zoom 함수 재사용
        def compression_to_zoom(comp):
            if comp <= 0.15:
                return 0.5 + (comp / 0.15) * 0.5
            elif comp <= 0.35:
                return 1.0 + ((comp - 0.15) / 0.20) * 1.0
            elif comp <= 0.5:
                return 2.0 + ((comp - 0.35) / 0.15) * 1.0
            elif comp <= 0.7:
                return 3.0 + ((comp - 0.5) / 0.2) * 2.0
            else:
                return 5.0 + ((comp - 0.7) / 0.3) * 5.0

        # 정확한 줌 배율 계산
        exact_zoom = compression_to_zoom(compression)

        # 초점거리 계산 (24mm = 1x 기준)
        estimated_focal_length = round(exact_zoom * 24)

        # 렌즈 타입 분류 (줌 배율 기준)
        if exact_zoom < 0.7:
            lens_type = "초광각"
            characteristics = "매우 넓은 화각, 배경 확장"
        elif exact_zoom < 1.2:
            lens_type = "표준"
            characteristics = "자연스러운 시야각"
        elif exact_zoom < 2.5:
            lens_type = "2배 망원"
            characteristics = "약간 압축된 배경"
        elif exact_zoom < 4:
            lens_type = "3배 망원"
            characteristics = "압축된 배경, 얕은 심도"
        elif exact_zoom < 7:
            lens_type = "5배 망원"
            characteristics = "매우 압축된 배경"
        else:
            lens_type = "10배 초망원"
            characteristics = "극도로 압축된 배경"

        return {
            "compression_value": compression,
            "focal_length_mm": estimated_focal_length,
            "lens_type": lens_type,
            "characteristics": characteristics,
            "exact_zoom": round(exact_zoom, 1),
            "depth_of_field": "얕음" if compression > 0.6 else "보통" if compression > 0.3 else "깊음"
        }

    def get_pose_type_description(self, pose_type: str) -> str:
        """포즈 타입을 구체적으로 설명하는 함수

        Note:
        - 현재 bbox 높이 기반 단순 판단 (RTMPose 의존성 미해결)
        - classified_full_v4의 분류 체계와 매칭
        - TODO: Phase 5에서 RTMPose 통합 시 정밀 판단 구현
        """

        pose_descriptions = {
            # classified_full_v4 기준 4가지 타입 (영어)
            "closeup": "클로즈업 (얼굴과 어깨 중심, 상체 일부만 보임)",
            "medium_shot": "상반신샷 (가슴~허리선까지 보임)",
            "knee_shot": "3/4 전신샷 (무릎 위까지 보임)",
            "full_shot": "전신샷 (머리부터 발끝까지 전체가 보임)",

            # 한글 버전 (reference_comparison.py 호환)
            "클로즈업": "클로즈업 (얼굴과 어깨 중심)",
            "미디엄샷": "상반신샷 (가슴~허리선)",
            "무릎샷": "3/4 전신샷 (무릎 위까지)",
            "전신샷": "전신샷 (전체가 보임)",

            # 기타
            "unknown": "샷 타입 판별 불가",
            "N/A": "샷 타입 정보 없음"
        }

        # 정확한 매칭
        if pose_type in pose_descriptions:
            return pose_descriptions[pose_type]

        # 대소문자 무시 매칭
        pose_lower = pose_type.lower() if pose_type else ""
        for key, desc in pose_descriptions.items():
            if pose_lower == key.lower():
                return desc

        # 기본값
        return f"{pose_type} (상세 정보 없음)"

    def generate_compression_adjustment(self, current_comp: float, target_comp: float,
                                       device_type: str = "generic") -> Dict[str, any]:
        """압축감 조정을 위한 정확한 방법 제시"""

        current = self.analyze_compression_accurately(current_comp, device_type)
        target = self.analyze_compression_accurately(target_comp, device_type)

        # 정확한 줌 배율 계산
        zoom_calc = self.calculate_exact_zoom_ratio(current_comp, target_comp)

        diff = target_comp - current_comp

        if abs(diff) < 0.05:
            return {"needs_adjustment": False, "message": "압축감 적절"}

        methods = []

        # 방법 1: 정확한 줌 조정
        zoom_instruction = {
            "method": "줌 조정",
            "current": f"{current['lens_type']} ({current['exact_zoom']}x)",
            "target": f"{target['lens_type']} ({target['exact_zoom']}x)",
            "action": zoom_calc['zoom_direction'],
            "steps": []
        }

        if diff > 0:  # 더 압축 필요
            zoom_instruction["steps"] = [
                f"1. 현재 {current['exact_zoom']}x를 {zoom_calc['zoom_ratio']}배 확대",
                f"2. 최종 목표: {target['exact_zoom']}x",
                f"3. 두 손가락으로 화면을 벌리거나 줌 버튼 사용",
                f"4. 효과: {target['characteristics']}"
            ]
        else:  # 덜 압축 필요
            zoom_instruction["steps"] = [
                f"1. 현재 {current['exact_zoom']}x를 {zoom_calc['zoom_ratio']}배 축소",
                f"2. 최종 목표: {target['exact_zoom']}x",
                f"3. 두 손가락으로 화면을 오므리거나 줌 버튼 사용",
                f"4. 효과: {target['characteristics']}"
            ]

        methods.append(zoom_instruction)

        # 방법 2: 거리 조정
        distance_change = "가까이" if diff > 0 else "멀리"
        distance_instruction = {
            "method": "거리 조정 (줌 대신)",
            "action": f"피사체에 {distance_change} 접근",
            "steps": [
                f"1. 줌을 {current['exact_zoom']}x로 유지",
                f"2. 피사체에 {distance_change} 이동",
                f"3. 배경이 {'더 압축되도록' if diff > 0 else '더 넓게 보이도록'} 조정",
                f"4. 목표: {target['characteristics']}"
            ],
            "note": "거리 조정은 원근감도 함께 변화시킵니다"
        }
        methods.append(distance_instruction)

        # 방법 3: 조합
        if abs(diff) > 0.2:  # 큰 차이일 때
            combined = {
                "method": "줌 + 거리 조합",
                "steps": [
                    f"1. 먼저 줌을 {target['exact_zoom']}x로 조정",
                    f"2. 그 다음 거리를 미세 조정하여 원하는 압축감 달성",
                    f"3. 최종 목표: {target['lens_type']} 효과"
                ],
                "advantage": "가장 정확한 압축감 재현 가능"
            }
            methods.append(combined)

        return {
            "needs_adjustment": True,
            "current_analysis": current,
            "target_analysis": target,
            "zoom_calculation": zoom_calc,
            "methods": methods,
            "primary_recommendation": methods[0] if methods else None
        }


def print_improved_feedback_v2(result: ComparisonResult, device_type: str = "generic"):
    """개선된 피드백 v2 출력"""

    feedback_gen = ImprovedFeedbackV2()

    print("\n" + "="*70)
    print("[AI 분석 결과] 개선된 v2")
    print("="*70)

    # 1. 기본 점수 및 이미지 타입
    score = result.similarity_score
    print(f"\n[유사도] {score:.0f}/100")
    print(f"[개선 가능] {result.improvement_potential:.0f}점")

    # 포즈 타입 표시 (개선된 버전)
    if 'pose' in result.detailed_feedback:
        pose_data = result.detailed_feedback['pose']
        current_pose = pose_data.get('current', 'N/A')
        reference_pose = pose_data.get('reference', 'N/A')

        print(f"\n[샷 타입 분석]")

        # 구체적인 설명 추가
        current_desc = feedback_gen.get_pose_type_description(current_pose)
        reference_desc = feedback_gen.get_pose_type_description(reference_pose)

        print(f"   내 사진: {current_desc}")
        print(f"   레퍼런스: {reference_desc}")

        # 타입이 다른 경우 조정 방법 제시
        if current_pose != reference_pose and current_pose != 'N/A' and reference_pose != 'N/A':
            print(f"\n   [주의] 샷 타입 불일치!")

            # 간단한 조정 가이드
            current_type = current_pose.lower().replace('샷', '').replace('_shot', '')
            ref_type = reference_pose.lower().replace('샷', '').replace('_shot', '')

            adjustment_guide = {
                ('closeup', 'medium'): "카메라를 뒤로 물러나거나 줌아웃하여 상반신이 보이도록",
                ('closeup', 'knee'): "카메라를 더 뒤로 물러나거나 줌아웃하여 무릎까지 보이도록",
                ('closeup', 'full'): "카메라를 충분히 뒤로 물러나거나 줌아웃하여 전신이 보이도록",
                ('medium', 'closeup'): "카메라를 가까이 하거나 줌인하여 얼굴과 어깨 위주로",
                ('medium', 'knee'): "카메라를 조금 뒤로 물러나거나 줌아웃하여 무릎까지",
                ('medium', 'full'): "카메라를 뒤로 물러나거나 줌아웃하여 전신이 보이도록",
                ('knee', 'closeup'): "카메라를 가까이 하거나 줌인하여 얼굴 위주로",
                ('knee', 'medium'): "카메라를 조금 가까이 하거나 줌인하여 상반신 위주로",
                ('knee', 'full'): "카메라를 조금 뒤로 물러나 발끝까지 보이도록",
                ('full', 'closeup'): "카메라를 많이 가까이 하거나 줌인하여 얼굴 위주로",
                ('full', 'medium'): "카메라를 가까이 하거나 줌인하여 상반신 위주로",
                ('full', 'knee'): "카메라를 조금 가까이 하거나 줌인하여 무릎 위까지만",
            }

            # 키 생성 시도
            for key_variations in [
                (current_type, ref_type),
                (current_type.replace('미디엄', 'medium'), ref_type.replace('미디엄', 'medium')),
                (current_type.replace('클로즈업', 'closeup'), ref_type.replace('클로즈업', 'closeup')),
                (current_type.replace('무릎', 'knee'), ref_type.replace('무릎', 'knee')),
                (current_type.replace('전신', 'full'), ref_type.replace('전신', 'full'))
            ]:
                if key_variations in adjustment_guide:
                    print(f"   [조정 방법] {adjustment_guide[key_variations]}")
                    break
            else:
                print(f"   [조정 방법] 레퍼런스와 동일한 구도로 촬영 거리 조정")

    # 2. 종횡비 체크
    print("\n" + "="*70)
    print("[1] 화면 비율")
    print("="*70)

    aspect_ratio_matched = True
    if result.priority_actions:
        for action in result.priority_actions:
            if action['type'] == 'aspect_ratio':
                aspect_ratio_matched = False
                print(f"현재: {action.get('current', 'N/A')}")
                print(f"목표: {action.get('target', 'N/A')}")
                print("\n[조정 방법]")
                print("  1. 카메라 설정 열기")
                print("  2. '사진 크기' 또는 'Aspect Ratio' 메뉴 선택")
                print(f"  3. {action.get('target', 'N/A')} 선택")
                print(f"  4. 효과: {action.get('impact', 'N/A')}")
                break

    if aspect_ratio_matched:
        print("\n[확인] 화면 비율이 레퍼런스와 일치합니다!")

    # 3. 위치 피드백 (버그 수정된 버전)
    print("\n" + "="*70)
    print("[2] 구도 및 위치 조정")
    print("="*70)

    position_matched = True
    if 'position' in result.detailed_feedback:
        pos_data = result.detailed_feedback['position']

        # 레거시 시스템은 'current', 'reference'를 문자열로 반환
        # 예: "(0.50, 0.50)"
        import re

        curr_str = pos_data.get('current', '')
        ref_str = pos_data.get('reference', '')

        # 문자열에서 숫자 추출
        curr_match = re.findall(r'([0-9.]+)', curr_str)
        ref_match = re.findall(r'([0-9.]+)', ref_str)

        if len(curr_match) >= 2 and len(ref_match) >= 2:
            curr_pos = (float(curr_match[0]), float(curr_match[1]))
            ref_pos = (float(ref_match[0]), float(ref_match[1]))
            current_grid = feedback_gen.convert_position_to_grid(curr_pos[0], curr_pos[1])
            target_grid = feedback_gen.convert_position_to_grid(ref_pos[0], ref_pos[1])

            movement = feedback_gen.calculate_camera_movement(curr_pos, ref_pos)

            if movement['needs_adjustment']:
                position_matched = False
                print(f"\n현재 인물 위치: {current_grid['description']} ({current_grid['grid_description']})")
                print(f"목표 인물 위치: {target_grid['description']} ({target_grid['grid_description']})")

                if target_grid['is_golden']:
                    print("  [황금비 위치]")

                print("\n[조정 방법]")
                for i, inst in enumerate(movement['instructions'], 1):
                    print(f"\n  방법 {i}: {inst['type'].upper()}")
                    if inst['type'] == 'vertical':
                        print(f"    - {inst['camera_movement']} ({inst['percentage']} 조정)")
                    else:
                        print(f"    - {inst['camera_movement']}")
                    print(f"    - 결과: {inst['subject_result']}")
                    print(f"    - 대안: {inst['alternative']}")
            else:
                print("\n[확인] 구도 및 위치가 레퍼런스와 유사합니다!")

    if position_matched and 'position' not in result.detailed_feedback:
        print("\n[확인] 인물 위치 정보가 없거나 매우 유사합니다!")

    # 4. 압축감/줌 피드백 (정확한 분석)
    print("\n" + "="*70)
    print("[3] 깊이감 및 배경 압축")
    print("="*70)

    compression_matched = True
    if 'compression' in result.detailed_feedback:
        comp_data = result.detailed_feedback['compression']
        curr_comp_str = comp_data.get('current', '')
        ref_comp_str = comp_data.get('reference', '')

        # 값 추출
        curr_match = re.search(r'\(([0-9.]+)\)', curr_comp_str)
        ref_match = re.search(r'\(([0-9.]+)\)', ref_comp_str)

        if curr_match and ref_match:
            curr_comp = float(curr_match.group(1))
            ref_comp = float(ref_match.group(1))

            # 정확한 줌 배율 계산
            zoom_calc = feedback_gen.calculate_exact_zoom_ratio(curr_comp, ref_comp)

            diff = abs(ref_comp - curr_comp)

            if diff > 0.05:  # 5% 이상 차이
                compression_matched = False

                print(f"\n[압축감 수치]")
                print(f"  현재: {curr_comp:.2f} → 레퍼런스: {ref_comp:.2f}")

                print(f"\n[24mm 기준 환산]")
                print(f"  현재: {zoom_calc['current_zoom']}x ({zoom_calc['current_focal_mm']}mm)")
                print(f"  목표: {zoom_calc['target_zoom']}x ({zoom_calc['target_focal_mm']}mm)")

                print(f"\n[필요한 조정]")

                # 3x 이상이 필요한 경우 거리 조정 권장
                if zoom_calc.get('needs_distance_adjustment', False):
                    print(f"  [주의] 목표 압축감이 높아 줌만으로는 한계가 있습니다")
                    print(f"     (이론적 목표: {zoom_calc.get('theoretical_target_zoom', zoom_calc['target_zoom'])}x)")
                    print(f"\n  권장 방법:")
                    print(f"  1. 줌을 최대 3x로 설정")
                    print(f"  2. 피사체에 더 가까이 접근하여 촬영")
                    print(f"  3. 또는 망원 렌즈 액세서리 사용 고려")
                else:
                    if zoom_calc['zoom_ratio'] > 1:
                        # 줌인이 필요한 경우
                        if zoom_calc['current_zoom'] < 0.5:
                            print(f"  [오류] 현재 줌이 최소값(0.5x)보다 낮게 계산됨")
                        else:
                            print(f"  > 현재 {zoom_calc['current_zoom']}x → {zoom_calc['target_zoom']}x로 줌인")
                    elif zoom_calc['zoom_ratio'] < 1:
                        # 줌아웃이 필요한 경우
                        if zoom_calc['target_zoom'] < 0.5:
                            print(f"  [주의] 더 넓은 화각이 필요합니다")
                            print(f"  권장: 0.5x 초광각으로 설정 후 뒤로 물러나기")
                        else:
                            print(f"  < 현재 {zoom_calc['current_zoom']}x → {zoom_calc['target_zoom']}x로 줌아웃")
                    else:
                        print(f"  [확인] 현재 줌 설정 유지 ({zoom_calc['current_zoom']}x)")

                    print(f"\n[조작 방법]")
                    print(f"  1. 두 손가락으로 화면을 {'벌려서' if zoom_calc['zoom_ratio'] > 1 else '모아서'} 조정")
                    print(f"  2. 또는 줌 버튼에서 {zoom_calc['target_zoom']}x 선택")
                    if zoom_calc['target_zoom'] not in [0.5, 1.0, 2.0, 3.0]:
                        print(f"  3. 정확한 배율이 없다면 가장 가까운 값 선택")

                # 특성 변화
                current_analysis = feedback_gen.analyze_compression_accurately(curr_comp)
                target_analysis = feedback_gen.analyze_compression_accurately(ref_comp)

                print(f"\n[효과]")
                print(f"  - 배경: {current_analysis['characteristics']} → {target_analysis['characteristics']}")
                print(f"  - 심도: {current_analysis['depth_of_field']} → {target_analysis['depth_of_field']}")
            else:
                print("\n[확인] 깊이감 및 배경 압축이 레퍼런스와 유사합니다!")
    else:
        print("\n[확인] 압축감 정보가 없거나 매우 유사합니다!")

    # 5. 종합 평가
    print("\n" + "="*70)
    print("[종합 평가]")
    print("="*70)

    if score >= 85:
        print("\n[탁월] 레퍼런스와 매우 유사합니다!")
        print("  미세 조정만으로 완벽한 결과 가능")
    elif score >= 70:
        print("\n[우수] 기본 구도가 잘 잡혀있습니다.")
        print("  위 가이드를 따라 몇 가지만 조정하세요.")
    elif score >= 55:
        print("\n[양호] 개선의 여지가 있습니다.")
        print("  우선순위에 따라 차근차근 조정해보세요.")
    else:
        print("\n[개선 필요] 큰 변화가 필요합니다.")
        print("  단계별로 천천히 따라해보세요.")

    # 가장 중요한 한 가지
    if result.priority_actions:
        print(f"\n[중요] 가장 먼저 할 일: {result.priority_actions[0]['action']}")


def main():
    """메인 실행 함수"""

    try:
        print("\n" + "="*70)
        print("  TryAngle v1.5 - 개선된 이미지 비교 도구 v2  ")
        print("="*70)
        print("\n비판적 검토를 반영한 더 정확한 피드백을 제공합니다.")
        print("="*70)

        # 이미지 경로 입력
        print("\n이미지 경로 입력")
        print("-" * 40)

        current_path = input("현재 이미지: ").strip().replace('"', '').replace("'", '')
        if not Path(current_path).exists():
            print(f"파일을 찾을 수 없습니다: {current_path}")
            return

        reference_path = input("레퍼런스 이미지: ").strip().replace('"', '').replace("'", '')
        if not Path(reference_path).exists():
            print(f"파일을 찾을 수 없습니다: {reference_path}")
            return

        # 기기 타입 선택 (옵션)
        print("\n촬영 기기 선택 (선택사항, Enter로 건너뛰기):")
        print("  1. iPhone")
        print("  2. Galaxy")
        print("  3. 기타/일반")
        device_choice = input("선택 (1-3): ").strip()

        device_type = "generic"
        if device_choice == "1":
            device_type = "iPhone"
        elif device_choice == "2":
            device_type = "Galaxy"

        # 분석 실행
        print("\n[AI 분석 중...]")
        print("-" * 40)

        comparator = ReferenceComparison()
        start_time = time.time()

        result = comparator.compare(
            current_path=current_path,
            reference_path=reference_path,
            mode='detailed'
        )

        total_time = time.time() - start_time

        # 개선된 피드백 v2 출력
        print_improved_feedback_v2(result, device_type)

        print(f"\n분석 시간: {total_time:.1f}초")

        # 재실행 여부
        print("\n" + "="*70)
        again = input("\n다른 이미지를 비교하시겠습니까? (y/n): ").lower()
        if again == 'y':
            main()
        else:
            print("\n감사합니다!")

    except KeyboardInterrupt:
        print("\n\n종료합니다.")
    except Exception as e:
        print(f"\n오류: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()