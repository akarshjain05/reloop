import time
import boto3
from .types import AIProvider, ItemAnalysis, BinAnalysis, AIUnavailable, build_bin_categories

class RekognitionProvider(AIProvider):
    name = "rekognition"
    model_id = "aws-rekognition"
    supports_chat = False

    def __init__(self, region: str):
        self.client = boto3.client("rekognition", region_name=region)

    def analyze_item(self, image: bytes, content_type: str, filename: str | None = None, hint: str | None = None) -> ItemAnalysis:
        t0 = time.time()
        try:
            res = self.client.detect_labels(Image={'Bytes': image}, MaxLabels=10, MinConfidence=50)
        except Exception as e:
            raise AIUnavailable(f"Rekognition failed: {e}")
        
        labels = [lbl["Name"].lower() for lbl in res.get("Labels", [])]
        
        item_type = labels[0] if labels else "unknown"
        confidence = res["Labels"][0]["Confidence"] / 100.0 if labels else 0.5
        
        # Simple mapping to known demo dataset categories to ensure pricing/impact works perfectly
        top_labels = labels[:3]
        if "laptop" in top_labels or "computer" in top_labels:
            item_type = "laptop"
        elif "phone" in top_labels or "mobile phone" in top_labels:
            item_type = "phone"
        elif "cable" in top_labels or "wire" in top_labels:
            item_type = "cable"
        elif "mouse" in top_labels:
            item_type = "mouse"
        elif "headphones" in top_labels or "headset" in top_labels:
            item_type = "headphones"
        
        latency = int((time.time() - t0) * 1000)
        return ItemAnalysis(
            item_type=item_type,
            label=f"Found: {', '.join(labels[:3])}",
            confidence=confidence,
            condition="used",
            provider=self.name,
            model_id=self.model_id,
            latency_ms=latency
        )

    def analyze_bin(self, image: bytes, content_type: str, filename: str | None = None) -> BinAnalysis:
        t0 = time.time()
        try:
            res = self.client.detect_labels(Image={'Bytes': image}, MaxLabels=20, MinConfidence=50)
        except Exception as e:
            raise AIUnavailable(f"Rekognition failed: {e}")
            
        labels = [lbl["Name"].lower() for lbl in res.get("Labels", [])]
        present = {}
        
        if "plastic" in labels or "bottle" in labels: present["plastic"] = (True, 0.9, "")
        if "paper" in labels or "cardboard" in labels or "box" in labels: present["paper"] = (True, 0.9, "")
        if "electronics" in labels or "computer" in labels or "phone" in labels: present["e_waste"] = (True, 0.9, "Electronics detected")
        if "battery" in labels: present["hazardous"] = (True, 0.95, "Battery detected")
        
        latency = int((time.time() - t0) * 1000)
        return BinAnalysis(
            categories=build_bin_categories(present),
            advice="Analysis by AWS Rekognition.",
            provider=self.name,
            model_id=self.model_id,
            latency_ms=latency
        )
