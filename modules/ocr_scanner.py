import re
import os
import tempfile
from datetime import datetime
from PIL import Image
import pytesseract
import streamlit as st
from modules.study_filters import scan_additives, has_sucralose


def scan_label(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang="ces+eng")
    except Exception as e:
        return {"error": f"OCR selhal: {e}", "text": "", "additives": {}, "has_sucralose": False, "safe": True}

    return _analyze_text(text)


def _analyze_text(text):
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


def _show_scan(r):
    c1, c2 = st.columns(2)
    with c1:
        if r["harmful"]: st.error(f"Nevhodna ({len(r['harmful'])})")
        for d in r["harmful"].values(): st.markdown(f"- {d}")
        if r["warnings"]: st.warning(f"Ke zvazeni ({len(r['warnings'])})")
        for d in r["warnings"].values(): st.markdown(f"- {d}")
        if r["safe_additives"]: st.success(f"Bezpecna ({len(r['safe_additives'])})")
        for d in r["safe_additives"].values(): st.markdown(f"- {d}")
    with c2:
        if r["has_sucralose"]: st.error("SUCRALOZA!")
        st.success("OK") if r["is_safe"] else st.warning("Problem")


def render_scanner(db):
    st.markdown("### OCR Label Scanner")
    st.caption("Sken slozeni s anti-sukraloza filtrem")
    method = st.radio("", ["Nahrat obrazek", "Vlozit text"], horizontal=True)
    if method == "Nahrat obrazek":
        up = st.file_uploader("Fotka", type=["png", "jpg", "jpeg", "webp"])
        if up:
            with st.spinner("Zacinam sken..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(up.read()); path = tmp.name
                r = scan_label(path); os.unlink(path)
                if "error" in r:
                    st.error(r["error"])
                else:
                    if r["text"]:
                        with st.expander("Rozpoznany text", expanded=False):
                            st.text(r["text"])
                    _show_scan(r)
                    db.add_scan_log(datetime.now().isoformat(), "OCR", r["text"][:1000], list(r["additives"].keys()), r["is_safe"])
    else:
        txt = st.text_area("Slozeni", placeholder="voda, cukr, maltodextrin, sukraloza...", height=100)
        if txt and st.button("Analyzovat"):
            r = _analyze_text(txt)
            _show_scan(r)
            db.add_scan_log(datetime.now().isoformat(), "Text", txt[:1000], list(r["additives"].keys()), r["is_safe"])
