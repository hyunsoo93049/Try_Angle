import mediapipe as mp
import cv2
import numpy as np

print("MediaPipe 테스트 시작...")

# MediaPipe Pose 초기화
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

print("✅ MediaPipe 초기화 완료!")

# 테스트 이미지 생성
print("\n테스트 이미지 생성 중...")
test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
cv2.imwrite('test_pose.jpg', test_image)
print("✅ 테스트 이미지 생성 완료: test_pose.jpg")

# 포즈 검출 실행
print("\n포즈 검출 실행 중...")
image_rgb = cv2.cvtColor(test_image, cv2.COLOR_BGR2RGB)
results = pose.process(image_rgb)

# 결과 출력
print("\n=== 검출 결과 ===")
if results.pose_landmarks:
    print(f"✅ 포즈 검출 성공!")
    print(f"총 {len(results.pose_landmarks.landmark)}개의 키포인트 검출됨")
else:
    print("검출된 포즈 없음 (정상 - 랜덤 이미지이므로)")

pose.close()
print("\n✅ MediaPipe 테스트 완료!")
