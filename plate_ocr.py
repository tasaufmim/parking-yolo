"""
License Plate OCR using OpenAI API with PaddleOCR Fallback
"""
import os
import base64
import json
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np

from plate_paddleocr import PaddleOCRPlugin


class PlateOCR:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = "gpt-4o-mini"
        self.colors_plate = ["white", "yellow", "black", "blue", "green", "red"]
        self.colors_text = ["black", "white", "yellow", "red", "green", "blue", "gold"]
        self.results = {}
        self.pending = set()
        self.paddle_fallback = PaddleOCRPlugin()
        self.prompt = """Analyze this Indian license plate image and provide:
1. License plate text (OCR) - exactly as shown on the plate
2. License plate background color - one of: white, yellow, black, blue, green, red
3. Text color on the plate - one of: black, white, yellow, red, green, blue, gold

IMPORTANT INDIAN LICENSE PLATE FORMATS:
- Standard: STATE_CODE RTO_CODE LETTERS NUM (e.g., DL01AB1234, MH12CD3456)
- BH series: NUM BH NUM LETTERS (e.g., 01BH1234AB)
- Commercial: STATE CODE NUM (e.g., TN 12 1234)
- Diplomatic: NUMCD (e.g., 1234CD)
- Army: STATE-NUM-NUM (e.g., HR-01-1234)
- Electric: STATE-EV-NUM (e.g., DL-EV-1234)

Indian State Codes (first 2 characters): 
AN, AP, AR, AS, BR, CH, CG, DD, DL, DN, GA, GJ, HR, HP, JH, JK, KA, KL, LD, ML, MN, MP, MZ, NL, OD, PB, PN, PY, RJ, SK, TN, TR, TS, UK, UP, WB, MH

Extract the exact text including spaces. If format is unclear, still extract visible characters.

Respond ONLY in this exact JSON format (no other text):
{"text": "PLATENUMBER", "plate_color": "COLOR", "text_color": "COLOR"}"""
    
    def _get_plate_log_path(self) -> str:
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        path = os.path.join("logs", date_str)
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, "plate_results.json")
    
    def _save_to_log(self, result: dict):
        log_path = self._get_plate_log_path()
        existing = []
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    existing = json.load(f)
            except:
                pass
        existing.append(result)
        with open(log_path, "w") as f:
            json.dump(existing, f, indent=2)
    
    def _get_valid_color(self, color: str, color_type: str) -> str:
        color_lower = color.lower() if color else ""
        valid = self.colors_plate if color_type == "plate" else self.colors_text
        for v in valid:
            if v in color_lower:
                return v
        return valid[0]
    
    def _encode_image(self, image: np.ndarray) -> str:
        _, buffer = cv2.imencode(".jpg", image)
        return base64.b64encode(buffer).decode("utf-8")
    
    async def analyze_async(self, plate_image, slot_id: str, car_id: str, image_filename: str = None):
        if not self.api_key:
            print("OPENAI_API_KEY not set")
            return self._use_fallback(plate_image, slot_id, car_id, image_filename, "API key not set")
        
        key = f"{slot_id}_{car_id}"
        if key in self.pending:
            return None
        
        self.pending.add(key)
        
        result = {
            "slot_id": slot_id,
            "car_id": car_id,
            "plate_text": "processing",
            "plate_color": "processing",
            "text_color": "processing",
            "timestamp": datetime.now().isoformat(),
            "image_file": image_filename,
            "source": "openai"
        }
        self.results[key] = result
        
        # Try OpenAI with 3 retries
        for attempt in range(3):
            try:
                result = await self._call_openai(plate_image, slot_id, car_id, image_filename)
                if result and result.get("plate_text") not in ["Error", "N/A", "Timeout"]:
                    result["source"] = "openai"
                    self.results[key] = result
                    self._save_to_log(result)
                    self.pending.discard(key)
                    return result
            except Exception as e:
                if attempt == 2:
                    error_msg = str(e)[:100]
                    print(f"[FALLBACK] {slot_id}/{car_id}: OpenAI failed - {error_msg}")
                    fallback_result = self._use_fallback(plate_image, slot_id, car_id, image_filename, error_msg)
                    self.pending.discard(key)
                    return fallback_result
                await asyncio.sleep(0.5)
        
        # If all retries fail, fallback to PaddleOCR
        fallback_result = self._use_fallback(plate_image, slot_id, car_id, image_filename, "All retries failed")
        self.pending.discard(key)
        return fallback_result

    async def _call_openai(self, plate_image, slot_id, car_id, image_filename):
        image_b64 = self._encode_image(plate_image)
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": self.prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }],
            "max_tokens": 100
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    try:
                        result_data = json.loads(text.strip().replace("```json", "").replace("```", ""))
                        return {
                            "slot_id": slot_id,
                            "car_id": car_id,
                            "plate_text": result_data.get("text", "N/A"),
                            "plate_color": self._get_valid_color(result_data.get("plate_color", "white"), "plate"),
                            "text_color": self._get_valid_color(result_data.get("text_color", "black"), "text"),
                            "timestamp": datetime.now().isoformat(),
                            "image_file": image_filename
                        }
                    except json.JSONDecodeError:
                        return {
                            "slot_id": slot_id,
                            "car_id": car_id,
                            "plate_text": "N/A",
                            "plate_color": "N/A",
                            "text_color": "N/A",
                            "timestamp": datetime.now().isoformat(),
                            "image_file": image_filename
                        }
                elif resp.status == 429:
                    raise Exception("Rate limit exceeded")
                elif resp.status == 401:
                    raise Exception("Invalid API key")
                else:
                    raise Exception(f"HTTP {resp.status}")
    
    def _use_fallback(self, plate_image, slot_id, car_id, image_filename, error):
        try:
            fallback_result = self.paddle_fallback.analyze(plate_image, slot_id, car_id, image_filename)
            if fallback_result:
                fallback_result["source"] = "paddleocr"
                fallback_result["fallback_reason"] = error
                self.results[f"{slot_id}_{car_id}"] = fallback_result
                self._save_to_log(fallback_result)
                return fallback_result
        except Exception as e:
            pass
        
        error_result = {
            "slot_id": slot_id,
            "car_id": car_id,
            "plate_text": "Error",
            "plate_color": "Error",
            "text_color": "Error",
            "timestamp": datetime.now().isoformat(),
            "image_file": image_filename,
            "source": "error",
            "error": error
        }
        self.results[f"{slot_id}_{car_id}"] = error_result
        self._save_to_log(error_result)
        return error_result
    
    def get_result(self, slot_id: str, car_id: str) -> dict:
        key = f"{slot_id}_{car_id}"
        return self.results.get(key, {
            "plate_text": "N/A",
            "plate_color": "N/A", 
            "text_color": "N/A"
        })
    
    def is_processing(self, slot_id: str, car_id: str) -> bool:
        key = f"{slot_id}_{car_id}"
        return key in self.pending
    
    def clear(self):
        self.results = {}
        self.pending = set()