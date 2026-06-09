import os
import sys
import tempfile
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS
from modules.database import Database
from modules.voice import init_voice, render_voice_button, speak
from modules.fermentation import (
    predict_ph_curve, estimate_completion, get_available_strains, get_sugar_types,
)
from modules.stool_tracker import (
    analyze_correlations, get_bristol_description, SYMPTOM_OPTIONS,
    PROBIOTIC_OPTIONS, FOOD_CATEGORIES,
)
from modules.ocr_scanner import scan_label
from modules.dna_import import parse_csv, parse_fasta, generate_sample_data
from modules.antinutrient import get_food_info, get_all_foods, search_food, GENERAL_TIPS
from modules.science_digest import generate_digest
from pubmed_sync import sync_if_needed

st.set_page_config(page_title="Symbiont.ai", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")

with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

# --- Session state ---
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

# --- Background PubMed sync ---
if "sync_done" not in st.session_state:
    st.session_state.sync_done = True
    try:
        added = sync_if_needed(db)
        if added > 0:
            st.toast(f"📡 PubMed: {added} novych studii", icon="🧬")
    except Exception:
        pass

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown('<p style="font-family:JetBrains Mono; font-size:1.1rem; color:#00F2FE; text-align:center; margin:0;">🧬 Symbiont.ai</p>', unsafe_allow_html=True)
    st.markdown('<p style="font-family:JetBrains Mono; font-size:0.65rem; color:#64748B; text-align:center;">Autonomni AI Jarvis</p>', unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    stats = db.get_stats()
    ec = stats.get("evidence_counts", {})
    col1, col2 = st.columns(2)
    with col1: st.metric("Studie", stats["total_studies"])
    with col2: st.metric("RCT/Meta", ec.get("RCT", 0) + ec.get("Meta-analysis", 0))

    render_voice_button()
    st.markdown('<p style="font-family:JetBrains Mono; font-size:0.6rem; color:#475569; text-align:center;">Klikni a mluv cesky</p>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("### 🧪 Rychly F2")
    qs = st.number_input("Cukr g/l", 20, 200, 80, label_visibility="collapsed")
    qt = st.slider("°C", 15, 50, 28, label_visibility="collapsed")
    if st.button("Simulovat", use_container_width=True):
        qr = predict_ph_curve(qs, qt, 5.5, ["Lactobacillus plantarum"])
        st.info(f"pH za 7d: {qr['final_ph']:.2f}")

    if not GEMINI_API_KEY:
        st.warning("⚠️ Chybi GEMINI_API_KEY v Secrets", icon="⚠️")

# ============ HEADER NAV ============
nav_items = [
    ("💬", "Chat"),
    ("🧬", "F2 Ferm"),
    ("📋", "Tracker"),
    ("📷", "Scanner"),
    ("🧪", "DNA"),
    ("🌱", "Anti-N"),
    ("📰", "Digest"),
]

nav_cols = st.columns(7)
for i, (icon, label) in enumerate(nav_items):
    with nav_cols[i]:
        btn_type = "primary" if MODULE == i else "secondary"
        if st.button(icon, key=f"nav_{i}", help=label, use_container_width=True, type=btn_type):
            st.session_state.current_module = i
            if st.session_state.cell_state in ("speaking",):
                st.session_state.cell_state = "idle"
                st.session_state.cell_label = "Symbiont ceka na dotaz..."
            st.rerun()

nav_label_cols = st.columns(7)
for i, (_, label) in enumerate(nav_items):
    with nav_label_cols[i]:
        active = " style='color:#00F2FE;font-weight:500'" if MODULE == i else ""
        st.markdown(f"<p style='font-family:JetBrains Mono;font-size:0.6rem;color:#475569;text-align:center;margin:0;' {active}>{label}</p>", unsafe_allow_html=True)

st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

# ============ CELL (always visible) ============
is_chat = MODULE == 0
cell_size_class = "cell-container--chat" if is_chat else ""
status_class = f"status-label--{st.session_state.cell_state}" if st.session_state.cell_state != "idle" else ""

cell_html = f"""
<div class="cell-container {cell_size_class}" onclick="SymbiontVoice.startListening()" title="Klikni a mluv na Symbionta">
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

# ============ MODULE 0: CHAT ============
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
                        reply = "❌ Chybny nebo chybejici Gemini API klic. Zaregistruj se na https://aistudio.google.com/apikey (zdarma)."
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

# ============ MODULE 1: F2 FERMENTATION ============
elif MODULE == 1:
    st.markdown("### F2 Fermentation Simulator")
    st.caption("Modelovani F2 kvaseni kombucha/tibi – pH krivka a predikce")
    col1, col2 = st.columns([1, 1])
    with col1:
        sugar_type = st.selectbox("Typ cukru", get_sugar_types(), key="ferm_sugar_type")
        sugar_g = st.slider("Cukr (g/l)", 20, 200, 80)
        temperature = st.slider("Teplota (°C)", 15, 50, 28)
        starting_ph = st.slider("Pocatecni pH", 3.5, 7.0, 5.5, 0.1)
        strains = st.multiselect("Kmeny", get_available_strains(), default=["Lactobacillus plantarum", "SCOBY (kombucha)"])
        days = st.slider("Delka (dny)", 1, 30, 7)
    with col2:
        if st.button("Spustit simulaci", use_container_width=True, key="ferm_go"):
            if not strains:
                st.warning("Vyber alespon jeden kmen")
            else:
                r = predict_ph_curve(sugar_g, temperature, starting_ph, strains, total_hours=days*24)
                m1, m2, m3 = st.columns(3)
                m1.metric("Min pH", f"{r['min_ph']:.2f}")
                m2.metric("Kon. pH", f"{r['final_ph']:.2f}")
                m3.metric("Rychlost", f"{r['fermentation_rate']:.2f}")
                st.info(r["status"])
                fig = go.Figure()
                x = [h/24 for h in r["time_points"]]
                fig.add_trace(go.Scatter(x=x, y=r["ph_curve"], mode="lines", name="pH", line=dict(color="#00F2FE", width=3), fill="tozeroy", fillcolor="rgba(0,242,254,0.1)"))
                fig.add_hline(y=3.5, line_dash="dash", line_color="#22C55E", annotation_text="Cil 3.5")
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=300, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
                if st.button("Ulozit", key="ferm_save"):
                    db.add_fermentation_log(datetime.now().isoformat(), sugar_g, temperature, r["final_ph"], ", ".join(strains), days*24, "")
                    st.success("Ulozeno")
    with st.expander("Historie"):
        logs = db.get_fermentation_logs()
        if logs:
            st.dataframe(pd.DataFrame(logs, columns=["ID","Datum","Cukr","Teplota","pH","Kmeny","Delka","Pozn"]).drop(columns=["ID"]), hide_index=True, use_container_width=True)

# ============ MODULE 2: STOOL TRACKER ============
elif MODULE == 2:
    st.markdown("### Stool & Symptom Tracker")
    st.caption("Bristol, priznaky, korelace se stravou a probiotiky")
    col1, col2 = st.columns([1, 1])
    with col1:
        ed = st.date_input("Datum", datetime.now())
        bs = st.select_slider("Bristol", list(range(1, 8)), 4, format_func=lambda x: f"{x} - {get_bristol_description(x).split(' (')[0]}")
        st.caption(get_bristol_description(bs))
        sym = st.multiselect("Priznaky", SYMPTOM_OPTIONS)
        fd = st.multiselect("Jidlo", FOOD_CATEGORIES)
        pb = st.multiselect("Probiotika", PROBIOTIC_OPTIONS)
        nt = st.text_area("Poznamky", max_chars=300)
        if st.button("Ulozit", use_container_width=True):
            db.add_stool_log(ed.isoformat(), bs, ", ".join(sym) or "zadne", ", ".join(fd) or "neuvedeno", ", ".join(pb) or "zadna", nt or "-")
            st.success("Ulozeno")
    with col2:
        logs = db.get_stool_logs(100)
        if logs:
            a = analyze_correlations(logs)
            if a:
                m1, m2, m3 = st.columns(3)
                m1.metric("Prumer", f"{a['avg_bristol']:.1f}"); m2.metric("Rozptyl", f"{a['std_bristol']:.2f}"); m3.metric("Trend", a["trend"])
                if a["daily_data"]:
                    df = pd.DataFrame(a["daily_data"])
                    fig = px.line(df, x="date", y="bristol", markers=True)
                    fig.add_hline(y=4, line_dash="dash", line_color="#22C55E")
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=250)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Potreba 3+ zaznamu")

# ============ MODULE 3: OCR ============
elif MODULE == 3:
    st.markdown("### OCR Label Scanner")
    st.caption("Sken slozeni s anti-sukraloza filtrem")
    method = st.radio("", ["Nahrat obrazek", "Vlozit text"], horizontal=True)
    if method == "Nahrat obrazek":
        up = st.file_uploader("Fotka", type=["png", "jpg", "jpeg", "webp"])
        if up:
            with st.spinner("..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(up.read()); path = tmp.name
                r = scan_label(path); os.unlink(path)
                if "error" in r:
                    st.error(r["error"])
                else:
                    if r["text"]:
                        with st.expander("Text", expanded=False):
                            st.text(r["text"])
                    _show_scan(r)
                    db.add_scan_log(datetime.now().isoformat(), "OCR", r["text"][:1000], list(r["additives"].keys()), r["is_safe"])
    else:
        txt = st.text_area("Slozeni", placeholder="voda, cukr, maltodextrin, sukraloza...", height=100)
        if txt and st.button("Analyzovat"):
            from modules.study_filters import scan_additives, has_sucralose
            add = scan_additives(txt)
            suc = has_sucralose(txt)
            harmful = {k:v for k,v in add.items() if v.startswith("❌")}
            warn = {k:v for k,v in add.items() if v.startswith("⚠️")}
            ok = {k:v for k,v in add.items() if v.startswith("✅")}
            safe = len(harmful) == 0
            c1, c2 = st.columns(2)
            with c1:
                if harmful: st.error(f"Nevhodna ({len(harmful)})"); [st.markdown(f"- {d}") for d in harmful.values()]
                if warn: st.warning(f"Ke zvazeni ({len(warn)})"); [st.markdown(f"- {d}") for d in warn.values()]
                if ok: st.success(f"Bezpecna ({len(ok)})"); [st.markdown(f"- {d}") for d in ok.values()]
            with c2:
                if suc: st.error("SUCRALOZA! Narusuje mikrobiom.")
                st.success("OK") if safe else st.warning("Problem")
            db.add_scan_log(datetime.now().isoformat(), "Text", txt[:1000], list(add.keys()), safe)

# ============ MODULE 4: DNA ============
elif MODULE == 4:
    st.markdown("### DNA Data Import")
    st.caption("Analyza mikrobiomu – alfa diverzita, F/B ratio")
    opt = st.radio("Vstup", ["Ukazkova data", "CSV", "FASTA"], horizontal=True)
    dna = None
    if opt == "Ukazkova data":
        if st.button("Generovat", use_container_width=True): dna = generate_sample_data()
    elif opt == "CSV":
        f = st.file_uploader("CSV", type=["csv","tsv"])
        if f: dna = parse_csv(f.read().decode("utf-8","ignore"))
    elif opt == "FASTA":
        f = st.file_uploader("FASTA", type=["fasta","fa","fna"])
        if f: dna = parse_fasta(f.read().decode("utf-8","ignore"))
    if dna:
        if "error" in dna:
            st.error(dna["error"])
        else:
            col1, col2 = st.columns(2)
            with col1:
                m1, m2, m3 = st.columns(3)
                m1.metric("Shannon", dna["shannon"]); m2.metric("Simpson", dna["simpson"]); m3.metric("Pielou", dna["pielou"])
                st.metric("Druhu", dna["n_species"])
                if dna.get("firmicutes_bacteroidetes_ratio"): st.metric("F/B", dna["firmicutes_bacteroidetes_ratio"])
            with col2:
                phyla = dna["phylum_distribution"]
                if phyla:
                    df = pd.DataFrame(phyla)
                    fig = go.Figure(data=[go.Pie(labels=df["phylum"], values=df["relative"], marker=dict(colors=df["color"]), hole=0.4)])
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", height=300)
                    st.plotly_chart(fig, use_container_width=True)
            spp = dna["species"]
            if spp:
                df = pd.DataFrame(spp).sort_values("relative", ascending=False).head(15)
                fig2 = px.bar(df, x="relative", y="taxon", orientation="h", color="relative", color_continuous_scale=["#1E293B","#00F2FE"])
                fig2.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=max(250, len(df)*25))
                st.plotly_chart(fig2, use_container_width=True)

# ============ MODULE 5: ANTINUTRIENT ============
elif MODULE == 5:
    st.markdown("### Antinutrient Deactivator")
    st.caption("Pruvodce deaktivaci fytatu, lektinu, oxalatu")
    col1, col2 = st.columns([1, 1.5])
    with col1:
        q = st.text_input("Hledat", placeholder="cocka, mandle, quinoa...")
        sel = None
        if q:
            m = search_food(q)
            if m: sel = st.selectbox("Vyber", m)
            else: st.warning("Nenalezeno")
        else:
            sel = st.selectbox("Nebo ze seznamu", [""]+get_all_foods())
            if sel == "": sel = None
    with col2:
        if sel:
            info = get_food_info(sel)
            if info:
                st.markdown(f"**{sel}**")
                ants = info["antinutrients"]
                st.markdown("Antinutrienty:")
                cols = st.columns(len(ants))
                for i, a in enumerate(ants):
                    with cols[i]: st.markdown(f"<div class='sci-fi-card' style='text-align:center;padding:0.4rem;'><span style='color:#EF4444;'>⚠️</span><br><span style='font-size:0.75rem;'>{a}</span></div>", unsafe_allow_html=True)
                d = info["deactivation"]
                st.markdown(f"**Metoda:** {d.get('metoda','')}")
                pc = st.columns(3)
                if "namaceni_hodiny" in d: pc[0].metric("Namaceni", f"{d['namaceni_hodiny']}h")
                if "vareni_minuty" in d: pc[1].metric("Vareni", f"{d['vareni_minuty']}m")
                if "tlakovy_hrnec_min" in d: pc[2].metric("Tlak", f"{d['tlakovy_hrnec_min']}m")
                if d.get("voda_vymenit"): st.info("💧 Slit vodu!")
                if "poznamka" in d: st.warning(d["poznamka"])
    st.markdown("<div class='divider-glow'></div>", unsafe_allow_html=True)
    st.markdown("#### Tipy")
    tc = st.columns(2)
    for i, tip in enumerate(GENERAL_TIPS):
        with tc[i%2]: st.markdown(f"<div class='sci-fi-card' style='padding:0.5rem;font-size:0.85rem;'>{tip}</div>", unsafe_allow_html=True)

# ============ MODULE 6: DIGEST ============
elif MODULE == 6:
    st.markdown("### Morning Science Digest")
    st.caption("Ranni souhrn nejnovejsich studii")
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Studii", db.get_stats()["total_studies"])
        if st.button("Generovat digest", use_container_width=True):
            with st.spinner("..."):
                st.session_state.current_digest = generate_digest(db, ai_client=st.session_state.gemini_model)
        if st.button("Sync PubMed", use_container_width=True):
            with st.spinner("Stahuji..."):
                a = sync_if_needed(db, force=True)
                st.success(f"Pridano {a} studii") if a else st.info("Zadne nove")
    with col2:
        if "current_digest" in st.session_state:
            d = st.session_state.current_digest
            st.markdown(f"<div class='sci-fi-card'>{d['digest']}</div>", unsafe_allow_html=True)
            if d.get("evidence_breakdown"):
                df = pd.DataFrame(list(d["evidence_breakdown"].items()), columns=["Level","Count"])
                fig = px.pie(df, values="Count", names="Level", color_discrete_sequence=["#22C55E","#00F2FE","#F59E0B","#EF4444"])
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", height=250)
                st.plotly_chart(fig, use_container_width=True)
            with st.expander("Studie"):
                for s in d["studies"]:
                    badge = "📊" if s.get("evidence_level") in ("RCT","Meta-analysis") else "📋"
                    st.markdown(f"{badge} **{s.get('title','')}**")
                    st.caption(f"{s.get('authors','')[:60]} | {s.get('journal','')} | {s.get('pub_date','')[:10]}")
        else:
            st.info("Klikni na Generovat digest")

# ============ FOOTER ============
st.markdown("<div class='divider-glow'></div>", unsafe_allow_html=True)
st.caption("🧬 Symbiont.ai | AI: Google Gemini Flash | Voice: Web Speech API | Data: PubMed")
