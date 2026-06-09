import os
import sys
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS
from modules.database import Database
from modules.voice import init_voice, render_voice_button, speak
from modules.fermentation import render_fermentation
from modules.stool_tracker import render_stool_tracker
from modules.ocr_scanner import render_scanner
from modules.dna_import import render_dna
from modules.antinutrient import render_antinutrient
from modules.science_digest import render_digest
from pubmed_sync import sync_if_needed

st.set_page_config(page_title="Symbiont.ai", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")

with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

for key in ["db", "messages", "gemini_model", "current_module", "cell_state", "cell_label", "current_digest"]:
    if key not in st.session_state:
        if key == "db":
            st.session_state.db = Database()
        elif key == "messages":
            st.session_state.messages = []
        elif key == "gemini_model":
            st.session_state.gemini_model = None
            st.session_state.gemini_model_name = None
            if GEMINI_API_KEY:
                models_to_try = [GEMINI_MODEL] + GEMINI_FALLBACK_MODELS
                for m in models_to_try:
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=GEMINI_API_KEY)
                        model = genai.GenerativeModel(m)
                        model.generate_content("test")
                        st.session_state.gemini_model = model
                        st.session_state.gemini_model_name = m
                        break
                    except Exception:
                        continue
        elif key == "current_module":
            st.session_state.current_module = 0
        elif key == "cell_state":
            st.session_state.cell_state = "idle"
        elif key == "cell_label":
            st.session_state.cell_label = "Symbiont ceka na dotaz..."

init_voice()
db = st.session_state.db
MODULE = st.session_state.current_module

if "sync_done" not in st.session_state:
    st.session_state.sync_done = True
    try:
        added = sync_if_needed(db)
        if added > 0:
            st.toast(f"📡 PubMed: {added} novych studii", icon="🧬")
    except Exception:
        pass

NAV_LABELS = ["Chat", "F2 Ferm", "Tracker", "Scanner", "DNA", "Anti-N", "Digest"]

def _switch_module(i):
    st.session_state.current_module = i
    if st.session_state.cell_state == "speaking":
        st.session_state.cell_state = "idle"
        st.session_state.cell_label = "Symbiont ceka na dotaz..."

with st.sidebar:
    st.markdown('<div class="sidebar-brand">Symbiont</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">Autonomni AI Jarvis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    current = st.radio(
        "_nav", range(7), index=MODULE,
        format_func=lambda i: NAV_LABELS[i],
        key="_nav_radio", label_visibility="collapsed",
    )
    if current != MODULE:
        _switch_module(current)
        st.rerun()

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    render_voice_button()
    st.markdown('<p class="sidebar-voice-label">Klikni a mluv cesky</p>', unsafe_allow_html=True)

    if not GEMINI_API_KEY:
        st.warning("⚠️ Chybi GEMINI_API_KEY v Secrets", icon="⚠️")

st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

stat_data = db.get_stats()
ec = stat_data.get("evidence_counts", {})
sc1, sc2, sc3, sc4 = st.columns(4)
with sc1:
    val = stat_data["total_studies"] or "Načítám..."
    lbl = "Studii v databazi" if stat_data["total_studies"] else "Synchronizuji PubMed..."
    st.markdown(f'<div class="stat-card"><div class="stat-value">{val}</div><div class="stat-label">{lbl}</div></div>', unsafe_allow_html=True)
with sc2:
    rct = ec.get("RCT", 0) + ec.get("Meta-analysis", 0)
    st.markdown(f'<div class="stat-card"><div class="stat-value">{rct}</div><div class="stat-label">RCT / Meta-analýzy</div></div>', unsafe_allow_html=True)
with sc3:
    st.markdown(f'<div class="stat-card"><div class="stat-value">{stat_data.get("fermentation_logs", 0)}</div><div class="stat-label">Fermentací</div></div>', unsafe_allow_html=True)
with sc4:
    st.markdown(f'<div class="stat-card"><div class="stat-value">{stat_data.get("stool_logs", 0)}</div><div class="stat-label">Záznamů stolice</div></div>', unsafe_allow_html=True)

is_chat = MODULE == 0
cell_size_class = "cell-container--chat" if is_chat else ""
status_class = f"status-label--{st.session_state.cell_state}" if st.session_state.cell_state != "idle" else ""

cell_html = f"""
<div class="cell-container {cell_size_class}" onclick="SymbiontVoice.handleCellClick()" title="Klikni a mluv na Symbionta">
    <div class="cell cell--{st.session_state.cell_state}">
        <div class="cell__membrane">
            <div class="cell__nucleus"></div>
            <div class="cell__organelle cell__organelle--1"></div>
            <div class="cell__organelle cell__organelle--2"></div>
            <div class="cell__organelle cell__organelle--3"></div>
            <div class="cell__organelle cell__organelle--4"></div>
        </div>
    </div>
</div>
<p class="status-label {status_class}">{st.session_state.cell_label}</p>
<p class="status-label" style="color:#334155;font-size:0.6rem;margin-top:-0.3rem;">klikni na bunku a mluv</p>
"""
st.markdown(cell_html, unsafe_allow_html=True)

if MODULE == 0:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Zeptej se na cokoliv o mikrobiomu...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.cell_state = "thinking"
        st.session_state.cell_label = "Symbiont analyzuje data..."
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner(""):
                try:
                    relevant = db.search_studies(prompt, n_results=5)
                    context = ""
                    if relevant:
                        context = "## Relevantni studie:\n"
                        for r in relevant[:5]:
                            context += f"- **{r['title']}** ({r['evidence_level']}, {r['pub_date']})\n"
                        context += "\n"

                    full_prompt = f"""Jsi Symbiont.ai, autonomni AI asistent specializovany na strevni mikrobiom,
fermentaci, rostlinnou vyzivu a medicinalni houby. Uzivatel je striktni vegan (14 let),
zajima se o F2 fermentaci, traveni rostlinnych bilkovin a eliminaci antinutrientu.

Pouzivej vedecke poznatky, latinskou nomenklaturu pro bakterie, a odkazuj na uroven dukazu.
Odpovidej cesky, srozumitelne a prakticky.

{context}
Uzivatel: {prompt}"""

                    if st.session_state.gemini_model:
                        response = st.session_state.gemini_model.generate_content(full_prompt)
                        reply = response.text
                    else:
                        reply = "⚠️ Chybi GEMINI_API_KEY. Zaregistruj se na https://aistudio.google.com/apikey (zdarma) a pridej klic do Streamlit Secrets."

                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    st.session_state.cell_state = "speaking"
                    st.session_state.cell_label = "Symbiont hovori..."
                    speak(reply)

                    if relevant:
                        with st.expander("📚 Zdroje z databaze"):
                            for r in relevant[:5]:
                                badge = "📊" if r["evidence_level"] in ("RCT", "Meta-analysis") else "📋"
                                st.markdown(f"{badge} **{r['title']}**")
                                st.caption(f"Evidence: {r['evidence_level']} | {r['pub_date']}")
                                st.markdown(f"[Otevrit]({r['url']})")
                                st.markdown("---")
                except Exception as e:
                    err = str(e)
                    if "API_KEY" in err:
                        reply = "❌ Chybny nebo chybejici Gemini API klic."
                    else:
                        reply = f"❌ {err}"
                    st.error(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

        st.session_state.cell_state = "idle"
        st.session_state.cell_label = "Symbiont ceka na dotaz..."
        st.rerun()

    if st.session_state.messages and st.button("🗑 Smazat", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()

elif MODULE == 1:
    render_fermentation(db)
elif MODULE == 2:
    render_stool_tracker(db)
elif MODULE == 3:
    render_scanner(db)
elif MODULE == 4:
    render_dna()
elif MODULE == 5:
    render_antinutrient()
elif MODULE == 6:
    render_digest(db)

st.markdown("<div class='divider-glow'></div>", unsafe_allow_html=True)
st.caption("🧬 Symbiont.ai | AI: Google Gemini Flash | Voice: Web Speech API | Data: PubMed")
