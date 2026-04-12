"""
PaddleOCR Fallback for License Plate Recognition
Used when OpenAI API fails or is unavailable
"""
import cv2
import re
import numpy as np
from datetime import datetime


class PaddleOCRPlugin:
    def __init__(self):
        try:
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(use_angle_cls=True, lang='en', det_db_thresh=0.3, rec_batch_num=1)
            self.available = True
            print("[PaddleOCR] Initialized successfully with server model")
        except Exception as e:
            print(f"[PaddleOCR] Not available: {e}")
            self.ocr = None
            self.available = False

    def _validate_indian_plate(self, text: str) -> str:
        """Validate and fix Indian license plate format"""
        if not text:
            return text
        
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        
        state_codes = ["AN", "AP", "AR", "AS", "BR", "CH", "CG", "DD", "DL", "DN",
                      "GA", "GJ", "HR", "HP", "JH", "JK", "KA", "KL", "LD", "ML",
                      "MN", "MP", "MZ", "NL", "OD", "PB", "PN", "PY", "RJ", "SK",
                      "TN", "TR", "TS", "UK", "UP", "WB", "MH"]
        
        if len(cleaned) < 6 or len(cleaned) > 15:
            return cleaned
        
        first_two = cleaned[:2]
        if first_two in state_codes:
            return cleaned
        
        return cleaned

    def analyze(self, plate_image, slot_id, car_id, image_filename=None):
        print(f"[PaddleOCR] Analyzing for {slot_id}/{car_id}")
        
        if not self.available or self.ocr is None:
            print(f"[PaddleOCR] Not available, returning error")
            return self._error_result(slot_id, car_id, image_filename, "PaddleOCR not available")
        
        try:
            print(f"[PaddleOCR] Running OCR on plate image...")
            result = self.ocr.ocr(plate_image)
            print(f"[PaddleOCR] Raw result type: {type(result)}")
            
            if not result or len(result) == 0:
                print(f"[PaddleOCR] No result, returning N/A")
                return self._na_result(slot_id, car_id, image_filename)
            
            first_result = result[0]
            print(f"[PaddleOCR] First result type: {type(first_result)}")
            
            text = None
            if isinstance(first_result, dict):
                rec_texts = first_result.get('rec_texts', [])
                print(f"[PaddleOCR] rec_texts: {rec_texts}")
                if rec_texts:
                    text = rec_texts[0]
            
            if not text:
                print(f"[PaddleOCR] No text extracted, returning N/A")
                return self._na_result(slot_id, car_id, image_filename)
            
            # Clean up text - remove trailing dots, spaces
            text = text.strip().rstrip('.')
            print(f"[PaddleOCR] Raw detected text: {text}")
            
            # Apply Indian plate validation
            validated_text = self._validate_indian_plate(text)
            print(f"[PaddleOCR] Validated text: {validated_text}")
            
            return {
                "slot_id": slot_id,
                "car_id": car_id,
                "plate_text": validated_text.strip(),
                "plate_color": "N/A",
                "text_color": "N/A",
                "timestamp": datetime.now().isoformat(),
                "image_file": image_filename,
                "source": "paddleocr"
            }
        except Exception as e:
            print(f"[PaddleOCR] Error: {e}")
            return self._error_result(slot_id, car_id, image_filename, str(e))

    def _na_result(self, slot_id, car_id, image_filename):
        return {
            "slot_id": slot_id,
            "car_id": car_id,
            "plate_text": "N/A",
            "plate_color": "N/A",
            "text_color": "N/A",
            "timestamp": datetime.now().isoformat(),
            "image_file": image_filename,
            "source": "paddleocr"
        }

    def _error_result(self, slot_id, car_id, image_filename, error):
        return {
            "slot_id": slot_id,
            "car_id": car_id,
            "plate_text": "N/A",
            "plate_color": "N/A",
            "text_color": "N/A",
            "timestamp": datetime.now().isoformat(),
            "image_file": image_filename,
            "source": "paddleocr",
            "error": error
        }