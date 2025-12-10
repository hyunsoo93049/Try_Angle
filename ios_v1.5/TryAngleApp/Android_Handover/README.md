# Android Handover Assets

This directory contains the essential UI assets for the Android port of TryAngle.

## UI_Assets
- **Logos**: Contains `Logo_Dark.png`. Use this for the Splash Screen and Gallery Header.
- **Icons**: Contains `Logo_Dark.png` (Source for App Icon). Please generate Android adaptive icons (mipmap) from this source file.

## Note for Android Developer
- The iOS implementation uses `AVFoundation` for camera preview. You should use `CameraX` on Android.
- The `GateSystem` logic (in `ios_porting_guide.md` or similar documentation) relies on 2D Pose Estimation. Use ML Kit Pose Detection or MediaPipe for equivalent functionality.
