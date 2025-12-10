# Android Porting Guide for TryAngle App

This document provides a comprehensive guide for porting the iOS `TryAngle` application (Swift/SwiftUI) to Android (Kotlin/Jetpack Compose). It outlines the core architecture, key algorithms, and specific implementation details required for a faithful migration.

## 1. Architecture Overview

-   **Pattern**: MVVM (Model-View-ViewModel).
-   **State Management**: The iOS app uses `Combine` (`@Published`, `ObservableObject`).
    -   *Android Logic*: Use `Kotlin Coroutines` and `StateFlow` / `LiveData`.
-   **Project Structure**:
    -   `Views/`: UI Components (SwiftUI -> Jetpack Compose).
    -   `Services/`: Core business logic (Camera, ML, Analysis).
    -   `Models/`: Data structures.

## 2. Core Features & Android Equivalents

| Feature | iOS Component (Swift) | Android Component (Kotlin) | Notes |
| :--- | :--- | :--- | :--- |
| **Camera** | `AVFoundation` (`AVCaptureSession`) | **CameraX** | Use `ProcessCameraProvider`. Custom aspect ratio handling required. |
| **UI** | `SwiftUI` | **Jetpack Compose** | 1:1 mapping is usually possible. |
| **ML Inference** | `TensorFlowLiteC` / `CoreML` | **TensorFlow Lite (Java/Kotlin API)** | Reuse `.tflite` models. |
| **Reactive** | `Combine` | **Coroutines / Flow** | |

---

## 3. Key Modules & Porting Logic

### A. Camera Manager (`CameraManager.swift`)
**Goal**: High-quality photo capture (12MP+) with smooth 60fps preview.

*   **Logic to Port**:
    1.  **Resolution Strategy**:
        *   iOS: Iterates `AVCaptureDevice.formats` to find highest photo dimension with 60fps support.
        *   Android: Use `ResolutionSelector` in CameraX. Prioritize `Quality.UHD` or `Quality.HIGHEST` for `ImageCapture`, but ensure `Preview` frame rate is maintained.
    2.  **Zoom (Hybrid)**:
        *   iOS: `videoZoomFactor` handles lens switching (Ultra Wide 0.5x <-> Wide 1.0x <-> Tele 3.0x).
        *   Android: `cameraControl.setZoomRatio()`. **Critical**: Android handles lens switching automatically in `DEFAULT` mode, but you must check `zoomState.minZoomRatio` to support 0.5x (Ultra Wide).
    3.  **Aspect Ratio**:
        *   iOS: Crops preview visually using `.videoGravity`.
        *   Android: Use `PreviewView.ScaleType`. For 16:9, use `FILL_CENTER` (Zoomed). For 4:3, use `FIT_CENTER` (WYSIWYG).
    4.  **Immediate Pause**:
        *   When switching tabs or entering background, `unbindAll()` must be called immediately to prevent resource locking (Error -17281 equivalent).

### B. Logic Core: Gate System (`GateSystem.swift`)
**Goal**: Evaluates photo composition in real-time (5 Gates).
*   **Status**: **Pure Logic**. Can be ported directly to a Kotlin `object` or `class`.
*   **Evaluation Steps**:
    1.  **Gate 0 (Aspect Ratio)**: Compare `current` vs `reference` ratio enum.
    2.  **Gate 1 (Framing)**:
        *   Calculates `box_area / screen_area`.
        *   *New Logic*: Uses "Shot Type" (Full Shot, Waist Shot, etc.) derived from **Pose Keypoints** (Ankles visible? Knees visible?).
        *   *Android*: Reuse the logic `ShotTypeGate.fromKeypoints`.
    3.  **Gate 2 (Position)**:
        *   Uses `MarginAnalyzer` (calculate top/bottom/left/right margins).
        *   Checks **Horizontal/Vertical Balance** vs Reference.
    4.  **Gate 3 (Compression/Depth)**:
        *   Compares `35mm Equivalent Focal Length`.
        *   *Android*: Read `CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS`. Android API returns physical focal length (mm). Convert to 35mm equivalent using sensor size:
            *   `Eq_35mm = (FocalLength / SensorWidth) * 36mm`
    5.  **Gate 4 (Pose)**:
        *   Compare Vector angles (Shoulder slope, Arm angles) between current and reference Pose Keypoints.
        *   Threshold: 15 degrees.

### C. ML Analyzer (`RealtimeAnalyzer.swift`)
**Goal**: Run YOLOX (Person Detection) -> RTMPose (Keypoints) -> Depth estimation.
*   **Pipeline**:
    *   Input: `CMSampleBuffer` (iOS) -> `ImageProxy` (Android/CameraX).
    *   **TFLite Integration**:
        *   Use the **Same .tflite models** provided in the repo.
        *   Android TFLite Interpreter supports GPU Delegate (recommended) or NNAPI.
    *   **Coordinate Normalization**:
        *   Ensure output coordinates (0.0 ~ 1.0) match the screen orientation. Android CameraX `ImageAnalysis` often needs rotation correction (`imageProxy.imageInfo.rotationDegrees`).

---

## 4. UI Migration Rules (SwiftUI -> Compose)

| UI Element | iOS (SwiftUI) | Android (Compose) |
| :--- | :--- | :--- |
| **Lists** | `ForEach` / `VStack` | `LazyColumn` / `Column` |
| **Overlays** | `ZStack` | `Box` |
| **Data Binding** | `@Binding var` | `val value: T`, `onValueChange: (T) -> Unit` |
| **Gestures** | `SimultaneousGesture` | `pointerInput { detectTransformGestures ... }` |
| **Grid** | `Path` (Custom Draw) | `Canvas` (Custom Draw) |

### Specific Components
1.  **Lens Selector (Zoom Button)**:
    *   iOS: Dynamic text (e.g., "1.5x").
    *   Android: Create a `Row` of `IconButton`s. Observe `zoomState` flow to update text.
2.  **Gate Progress/Feedback**:
    *   The 5-step progress bar (`GateProgressView.swift`) should be a reusable `Composable`.

---

## 5. Files to Reference

*   `Services/OnDevice/GateSystem.swift`: **Evaluation Logic (Source of Truth)**. Move logic 1:1.
*   `Services/CameraManager.swift`: Reference for "High Res + 60FPS" configuration logic.
*   `Views/GalleryView.swift`: Reference for "Close Button" and Tab switching logic.
*   `Services/RealtimeAnalyzer.swift`: Reference for TFLite Pre/Post-processing.

## 6. Known Issues / Watchlist
*   **Resource Contention**: Like iOS, ensure Camera is unbound before opening the Android Gallery (`Intent.ACTION_VIEW` or `PhotoPicker`).
*   **0.5x Zoom**: On some Android devices, the Ultra Wide camera is not exposed to 3rd party apps via CameraX. Check device compatibility.

---
*Created by Antigravity Assistant for Android Developer Handover.*
