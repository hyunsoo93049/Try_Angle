from rtmpose_utils import load_rtm_pose_model, run_rtm_pose
def main(image_path):
    print('모델 불러오기')
    model = load_rtm_pose_model('rtmpose-m')
    print('포즈 추론 시작')
    results = run_rtm_pose(model, image_path)
    
    # 출력 간략 예시: 첫 사람 검출 시 keypoints 출력
    for result in results:
        if hasattr(result, 'keypoints'):
            print(result.keypoints)
    print('RTM Pose 추론 완료!')

if __name__ == "__main__":
    main("data/sample_images/jott2.jpeg")