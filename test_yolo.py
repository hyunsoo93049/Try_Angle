from ultralytics import YOLO
import cv2
import numpy as np

print("Yolo 테스트 시작 ...")

#YOLO 모델 로드
print("모델 로딩 중 ...")
model = YOLO('yolov8s.pt') # yolov8 - small 버전 사전 학습모델 불러오기
print("모델 로드 완료")

#테스트 이미지 생성
print("\n테스트 이미지 생성중")
test_image = np.random.randint(0,255,(640,640,3),dtype=np.uint8)
cv2.imwrite('test_image.jpg', test_image)
print("✅ 테스트 이미지 생성 완료: test_image.jpg")

#객체 검출 실행
print("\n 객체 검출 실행 중...")
results = model('test_image.jpg')

#결과 출력
print("\n=== 검출 결과 ===")
for result in results:
    boxes = result.boxes
    if len(boxes) > 0:
        print(f"총{len(boxes)}개의 객체 검출됨")
        for box in boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            class_name = model.names[class_id]
            print(f"- {class_name}: {confidence: .2%}")
    else:
        print("검출된 객체 없음(정상 - 랜덤 이미지)")

print("\nYolo 테스트 완료")