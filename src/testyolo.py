from ultralytics import YOLO

# 모델 경로: Try_Angle/yolo_models/yolo11s.pt
model_path = "../yolo_models/yolo11s.pt"

# 테스트 이미지 경로: Try_Angle/data/sample_images/jott3.jpeg
image_path = "../data/sample_images/jott3.jpeg"

# 모델 로드
model = YOLO(model_path)

# 인퍼런스 실행
results = model(image_path)

# 결과 시각화 및 표시
results[0].show()    # 팝업으로 이미지 보여줌 (matplotlib 필요시 자동 install됨)
# 결과 저장 (옵션, 필요시)
# results[0].save(filename="../data/sample_images/jott3_detected.jpeg")
