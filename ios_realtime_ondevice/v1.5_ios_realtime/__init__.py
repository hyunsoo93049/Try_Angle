"""
TryAngle iOS Realtime Package
Version: 7.0
"""

from .core.smart_feedback_v7 import SmartFeedbackV7
from .realtime.cache_manager import CacheManager
from .realtime.frame_processor import FrameProcessor

__version__ = "7.0"
__all__ = ["SmartFeedbackV7", "CacheManager", "FrameProcessor"]