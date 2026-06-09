import re
from PIL import Image
import pytesseract
from modules.study_filters import scan_additives, has_sucralose


def scan_label(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang="ces+eng")
    except Exception as e:
        return {"error": f"OCR selhal: {e}", "text": "", "additives": {}, "has_sucralose": False, "safe": True}

    additives = scan_additives(text)
    sucralose_detected = has_sucralose(text)

    harmful = {k: v for k, v in additives.items() if v.startswith("❌")}
    warnings = {k: v for k, v in additives.items() if v.startswith("⚠️")}
    safe = {k: v for k, v in additives.items() if v.startswith("✅")}

    is_safe = len(harmful) == 0

    return {
        "text": text.strip(),
        "additives": additives,
        "harmful": harmful,
        "warnings": warnings,
        "safe_additives": safe,
        "has_sucralose": sucralose_detected,
        "is_safe": is_safe,
    }
