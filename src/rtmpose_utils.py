from ultralytics import RTMPose

## utils.py는 이미지를 불러오거나 저장, 크기변환시 사용
#RTM Pose 모델 로드
def load_rtm_pose_model(model_name='rtmpose-m'):
    model = RTMPose(model_name)
    return model

#이미지에서 RTM Pose 인퍼런스 실행
def run_rtm_pose(model, image_path):
    results = model(image_path)
    return results
