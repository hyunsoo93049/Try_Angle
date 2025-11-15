# =========================================================
# 🔮 TryAngle Cluster Matcher v3
# =========================================================

import os
import numpy as np
import joblib
import json
import sys

# Model cache
sys.path.append(r"C:\try_angle\src\Multi\version3")
from utils.model_cache import model_cache

# 🔥 절대 import로만 구성 (가장 안정적)
from feature_extraction.feature_extractor_v2 import extract_features_v2 as extract_features_full
from embedder.embedder import embed_features

# =============================================
# 1) 모델 경로 설정
# =============================================
FEATURE_MODEL_DIR = r"C:\try_angle\feature_models"

KMEANS_MODEL_PATH   = os.path.join(FEATURE_MODEL_DIR, "kmeans_model.pkl")
CENTROIDS_PATH      = os.path.join(FEATURE_MODEL_DIR, "kmeans_centroids.npy")
CLUSTER_INFO_PATH   = os.path.join(FEATURE_MODEL_DIR, "cluster_info.json")

# ---------------------------------------------------------
# [2] 모델 로딩 (싱글톤)
# ---------------------------------------------------------
def _load_cluster_models():
    """Cluster 모델 로드 (한 번만)"""
    print("🔧 Loading cluster matcher models...")

    kmeans_model = joblib.load(KMEANS_MODEL_PATH)
    centroids    = np.load(CENTROIDS_PATH)

    # interpretation(라벨)이 있으면 불러오고 없으면 None
    if os.path.exists(CLUSTER_INFO_PATH):
        with open(CLUSTER_INFO_PATH, "r", encoding="utf-8") as f:
            cluster_info = json.load(f)
    else:
        cluster_info = None

    print("✅ Cluster matcher models loaded successfully")

    return {
        "kmeans_model": kmeans_model,
        "centroids": centroids,
        "cluster_info": cluster_info
    }

# 싱글톤으로 로드
_cluster_models = None

def get_cluster_models():
    """Cluster 모델 가져오기 (싱글톤)"""
    return model_cache.get_or_load("cluster_matcher_models", _load_cluster_models)


# ---------------------------------------------------------
# [3] 클러스터 예측 함수
# ---------------------------------------------------------
def match_cluster_from_features(feature_dict):
    # 모델 가져오기 (캐시됨)
    models = get_cluster_models()
    kmeans_model = models["kmeans_model"]
    centroids = models["centroids"]
    cluster_info = models["cluster_info"]

    vec_128 = embed_features(feature_dict).reshape(1, -1)

    cluster_id = int(kmeans_model.predict(vec_128)[0])

    center = centroids[cluster_id]
    dist = float(np.linalg.norm(vec_128 - center))

    if cluster_info and str(cluster_id) in cluster_info:
        label = cluster_info[str(cluster_id)]
    else:
        label = f"cluster_{cluster_id}"

    return {
        "cluster_id": cluster_id,
        "distance": dist,
        "label": label,
        "raw_embedding": vec_128.flatten()
    }


# ---------------------------------------------------------
# [4] 이미지 파일 입력 전용
# ---------------------------------------------------------
def match_cluster_from_image(image_path):

    feat = extract_features_full(image_path)
    if feat is None:
        raise ValueError(f"❌ Feature extraction failed: {image_path}")

    return match_cluster_from_features(feat)


# ---------------------------------------------------------
# [5] 테스트
# ---------------------------------------------------------
if __name__ == "__main__":
    test_img = r"C:\try_angle\data\test_images\test1.jpg"
    result = match_cluster_from_image(test_img)

    print("\n🎯 Prediction Result")
    print(result)
