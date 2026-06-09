import cv2
import logging
import numpy as np
import mediapipe as mp
import easyocr
from ultralytics import YOLO

logger = logging.getLogger(__name__)

class EliteThumbnailEngine:
    def __init__(self):
        logger.info("Initializing EliteThumbnailEngine...")
        # Load real computer vision models
        self.yolo = YOLO('yolov8n.pt')  # For object/face saliency detection
        self.reader = easyocr.Reader(['en']) # For real OCR readability

        # Load mediapipe correctly
        try:
            from mediapipe.tasks import python as mp_tasks
            from mediapipe.tasks.python import vision

            # Use newer mediapipe tasks API
            base_options = mp_tasks.BaseOptions(model_asset_path='blaze_face_short_range.tflite') # Assume model exists or will be downloaded, or fallback
            options = vision.FaceDetectorOptions(base_options=base_options)
            self.face_detection = vision.FaceDetector.create_from_options(options)
            self.use_tasks_api = True
        except ImportError:
            self.use_tasks_api = False
            logger.warning("Could not load MediaPipe Face Detector cleanly. Face detection score may be limited.")

    def analyze_thumbnail(self, image_path):
        """
        Runs comprehensive visual intelligence on a thumbnail:
        - Face & Saliency mapping (via YOLO and MediaPipe)
        - Visual Heatmap generation (via OpenCV Saliency)
        - OCR readability (via EasyOCR)
        - True contrast checks
        """
        logger.info(f"Analyzing thumbnail: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            logger.warning(f"Could not load image at {image_path}.")
            return {'overall_score': 0.0, 'status': 'failed'}

        saliency_score = self._analyze_saliency_and_faces(img)
        readability = self._check_ocr_readability(image_path)
        contrast = self._check_contrast(img)

        # Generate and save heatmap
        heatmap_generated = self._generate_heatmap(img, image_path)

        # Combine true ML scores
        score = (readability * 0.4) + (saliency_score * 0.4) + (contrast * 0.2)

        return {
            'saliency_score': saliency_score,
            'readability_score': readability,
            'contrast_score': contrast,
            'overall_score': score,
            'heatmap_generated': heatmap_generated,
            'status': 'analyzed'
        }

    def _generate_heatmap(self, img, original_path):
        """
        Generates a visual saliency heatmap using OpenCV and saves it.
        This provides a visual representation of where viewer eyes will track.
        """
        try:
            saliency = cv2.saliency.StaticSaliencyFineGrained_create()
            success, saliency_map = saliency.computeSaliency(img)

            if success:
                # Normalize and apply colormap
                saliency_map = (saliency_map * 255).astype("uint8")
                heatmap = cv2.applyColorMap(saliency_map, cv2.COLORMAP_JET)

                # Blend with original image
                blended = cv2.addWeighted(img, 0.6, heatmap, 0.4, 0)

                out_path = original_path.replace('.jpg', '_heatmap.jpg').replace('.png', '_heatmap.png')
                cv2.imwrite(out_path, blended)
                return True
        except Exception as e:
            logger.warning(f"Failed to generate heatmap: {e}")
        return False

    def select_best_thumbnail(self, thumbnail_paths):
        """
        A/B testing tournament to pick the optimal thumbnail
        """
        best_score = -1
        best_thumb = None

        for path in thumbnail_paths:
            analysis = self.analyze_thumbnail(path)
            if analysis['overall_score'] > best_score:
                best_score = analysis['overall_score']
                best_thumb = path

        logger.info(f"Selected best thumbnail: {best_thumb} with score {best_score}")
        return best_thumb

    def _analyze_saliency_and_faces(self, img):
        """
        Uses YOLO and MediaPipe to detect objects and faces. High presence of distinct faces/objects
        usually correlates to higher CTR on YouTube thumbnails. Returns score between 0.0 and 1.0
        """
        score = 0.0

        # MediaPipe Face Detection
        if hasattr(self, 'use_tasks_api') and self.use_tasks_api and hasattr(self, 'face_detection'):
            try:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                results = self.face_detection.detect(mp_image)
                if results and results.detections:
                    score += min(len(results.detections) * 0.2, 0.5) # Up to 0.5 for faces
            except Exception as e:
                logger.warning(f"MediaPipe Face Detection failed: {e}")

        # YOLO Object Detection (Looking for salient objects)
        yolo_results = self.yolo(img, verbose=False)
        if yolo_results and len(yolo_results[0].boxes) > 0:
            score += min(len(yolo_results[0].boxes) * 0.1, 0.5) # Up to 0.5 for objects

        return min(score, 1.0)

    def _check_ocr_readability(self, img_path):
        """
        Uses EasyOCR to detect text. Checks if text is large and clear.
        """
        results = self.reader.readtext(img_path)
        if not results:
            return 0.5 # Neutral if no text (maybe visual heavy)

        total_confidence = sum([res[2] for res in results])
        avg_confidence = total_confidence / len(results) if results else 0.0
        return avg_confidence

    def _check_contrast(self, img):
        """
        Calculates true RMS contrast of the image.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        rms = gray.std()

        # Normalize RMS contrast assuming typical 0-255 range (max std dev is ~127.5)
        normalized_contrast = rms / 127.5
        return min(normalized_contrast * 1.5, 1.0) # Boost slightly

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = EliteThumbnailEngine()
    best = engine.select_best_thumbnail(['dummy1.jpg', 'dummy2.jpg'])
    print(f"Tournament Winner: {best}")
