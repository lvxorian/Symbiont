import os
import sys
import json
import tempfile
from datetime import datetime
from io import BytesIO

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.config import GEMINI_API_KEY, GEMINI_MODEL
from modules.database import Database
from modules.fermentation import (
    predict_ph_curve, estimate_completion, get_available_strains, get_sugar_types
)
from modules.stool_tracker import (
    analyze_correlations, get_bristol_description, SYMPTOM_OPTIONS,
    PROBIOTIC_OPTIONS, FOOD_CATEGORIES
)
from modules.ocr_scanner import scan_label
from modules.dna_import import parse_csv, parse_fasta, generate_sample_data
from modules.antinutrient import get_food_info, get_all_foods, search_food, GENERAL_TIPS
from modules.science_digest import generate_digest
from pubmed_sync import sync_if_needed

st.set_page_config(
    page_title="Symbiont.ai",
    page_icon="\U0001F9EC",
    layout="wide",
    initial_sidebar_state="expanded",
)

with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

# --- Init ---
if "db" not in st.session_state:
    st.session_state.db = Database()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "gemini_model" not in st.session_state:
    st.session_state.gemini_model = None
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            st.session_state.gemini_model = genai.GenerativeModel(GEMINI_MODEL)
        except Exception:
            pass

db = st.session_state.db

# --- Background sync ---
if "sync_attempted" not in st.session_state:
    st.session_state.sync_attempted = True
    try:
        added = sync_if_needed(db)
        if added > 0:
            st.toast(f"PubMed sync: {added} novych studii pridan!", icon="\U0001F9EC")
    except Exception:
        pass

# ============ WEB SPEECH API (browser voice input - 100% free) ============
SPEECH_HTML = """
<div style="text-align:center; padding:0.5rem;">
    <button id="speech-btn" onclick="startSpeech()" style="
        background: linear-gradient(135deg, #00F2FE22, #22C55E22);
        border: 1px solid #00F2FE44;
        color: #00F2FE;
        padding: 0.75rem 1.5rem;
        border-radius: 50px;
        cursor: pointer;
        font-size: 1.5rem;
        transition: all 0.3s ease;
        font-family: 'JetBrains Mono', monospace;
    ">
        🎤 Nahlas dotaz
    </button>
    <p id="speech-status" style="color:#94A3B8; font-size:0.85rem; margin-top:0.5rem;"></p>
    <input type="hidden" id="speech-result" value="">
</div>
<script>
function startSpeech() {
    const btn = document.getElementById('speech-btn');
    const status = document.getElementById('speech-status');
    const hidden = document.getElementById('speech-result');
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        status.textContent = '❌ Vase prohlizec nepodporuje rozpoznavani reci (zkus Chrome/Edge)';
        return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = 'cs-CZ';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    btn.textContent = '⏺️ ...';
    btn.style.borderColor = '#EF4444';
    btn.style.boxShadow = '0 0 20px #EF444444';
    status.textContent = '🎤 Nasloucham... (mluvte jasne)';
    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        hidden.value = transcript;
        status.textContent = '✅ Rozpoznano: "' + transcript + '"';
        btn.textContent = '🎤 Hotovo';
        btn.style.borderColor = '#22C55E44';
        btn.style.boxShadow = '0 0 20px #22C55E44';
        hidden.dispatchEvent(new Event('change', { bubbles: true }));
        setTimeout(function() {
            const inputs = document.querySelectorAll('input[type="text"], textarea');
            for (let inp of inputs) {
                if (inp.placeholder && inp.placeholder.includes('zeptej')) {
                    inp.value = transcript;
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    break;
                }
            }
        }, 300);
    };
    recognition.onerror = function(event) {
        status.textContent = '❌ Chyba: ' + event.error;
        btn.textContent = '🎤 Nahlas dotaz';
        btn.style.borderColor = '#00F2FE44';
        btn.style.boxShadow = 'none';
    };
    recognition.onend = function() {
        setTimeout(function() {
            btn.textContent = '🎤 Nahlas dotaz';
            btn.style.borderColor = '#00F2FE44';
            btn.style.boxShadow = 'none';
        }, 2000);
    };
    recognition.start();
}
</script>
"""

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
        <h1 style="font-size: 1.8rem; margin: 0;">🧬 Symbiont.ai</h1>
        <p style="color: #94A3B8; font-size: 0.75rem; font-family: 'JetBrains Mono', monospace;">
            Autonomni AI Jarvis pro Mikrobiom
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    stats = db.get_stats()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📚 Studie", stats["total_studies"])
    with col2:
        evidence_counts = stats.get("evidence_counts", {})
        rct_count = evidence_counts.get("RCT", 0) + evidence_counts.get("Meta-analysis", 0)
        st.metric("📊 RCT/Meta", rct_count)

    if stats["total_studies"] > 0:
        st.caption("Dukazni urovne:")
        for level, count in sorted(evidence_counts.items(), key=lambda x: x[1], reverse=True):
            icon = "📊" if level in ["Meta-analysis", "RCT"] else "📋"
            st.markdown(f"{icon} **{level}**: {count}", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("### 🎤 Hlasovy vstup")
    st.markdown("Funguje v Chrome/Edge - nahlas dotaz a ten se vlozi do chatu")
    st.components.v1.html(SPEECH_HTML, height=120)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("### 🧪 Rychly F2 odhad")
    quick_sugar = st.number_input("Cukr (g/l)", min_value=20, max_value=200, value=80, key="quick_sugar")
    quick_temp = st.slider("Teplota (°C)", 15, 50, 28, key="quick_temp")
    if st.button("🔬 Simulovat", key="quick_sim"):
        quick_result = predict_ph_curve(quick_sugar, quick_temp, 5.5, ["Lactobacillus plantarum"])
        st.info(f"pH za 7 dni: **{quick_result['final_ph']:.2f}** | {quick_result['status']}")

    if not GEMINI_API_KEY:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.warning("⚠️ Neni nastaven GEMINI_API_KEY - chat nebude fungovat", icon="⚠️")
        st.markdown("1. Zaregistruj se na [aistudio.google.com](https://aistudio.google.com/apikey)")
        st.markdown("2. Vytvor API klice (zcela zdarma)")
        st.markdown("3. Pridej do `.env` nebo Streamlit Secrets")

# ============ MAIN TABS ============
tab_names = [
    "💬 AI Chat",
    "🧬 F2 Fermentation",
    "📋 Stool Tracker",
    "📷 OCR Scanner",
    "🧪 DNA Import",
    "🌱 Antinutrient",
    "📰 Science Digest",
]
tabs = st.tabs(tab_names)

# ============ TAB 0: AI CHAT (Gemini - zcela zdarma) ============
with tabs[0]:
    st.markdown("### 💬 Symbiont AI Chat")
    st.caption("Dotazuj se na mikrobiom, fermentaci, antinutrienty a vedecke studie")
    st.info("🧠 Bezi na Google Gemini 1.5 Flash - 100% zdarma. API klic z aistudio.google.com", icon="ℹ️")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Zeptej se na cokoliv o mikrobiomu..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Symbiont premysli (Gemini Flash)..."):
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
                        reply = "⚠️ API klic pro Gemini neni nastaven. Zaregistruj se na https://aistudio.google.com/apikey (zdarma) a pridej klic do `.env` nebo Streamlit Secrets."

                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

                    if relevant:
                        with st.expander("📚 Zdroje z databaze"):
                            for r in relevant[:5]:
                                badge = "📊" if r["evidence_level"] in ["RCT", "Meta-analysis"] else "📋"
                                st.markdown(f"{badge} **{r['title']}**")
                                st.caption(f"Evidence: {r['evidence_level']} | {r['pub_date']}")
                                st.markdown(f"[Otevrit]({r['url']})")
                                st.markdown("---")

                except Exception as e:
                    err_msg = str(e)
                    if "API_KEY" in err_msg or "not found" in err_msg:
                        reply = "❌ Chybny nebo chybejici Gemini API klic. Zaregistruj se na https://aistudio.google.com/apikey (zdarma)."
                    else:
                        reply = f"❌ Chyba: {err_msg}"
                    st.error(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

    if st.button("🗑 Smazat konverzaci", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()

# ============ TAB 1: F2 FERMENTATION ============
with tabs[1]:
    st.markdown("### 🧬 F2 Fermentation Simulator")
    st.caption("Modelovani druhe faze kvaseni (kombucha/tibi) - predikce pH krivky")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Vstupni parametry")
        sugar_type = st.selectbox("Typ cukru", get_sugar_types())
        sugar_g = st.slider("Mnozstvi cukru (g/l)", 20, 200, 80)
        temperature = st.slider("Teplota kvaseni (°C)", 15, 50, 28)
        starting_ph = st.slider("Pocatecni pH", 3.5, 7.0, 5.5, 0.1)
        strains = st.multiselect(
            "Mikrobialni kmeny",
            get_available_strains(),
            default=["Lactobacillus plantarum", "SCOBY (kombucha)"],
        )
        duration_days = st.slider("Delka fermentace (dny)", 1, 30, 7)
        duration_hours = duration_days * 24

    with col2:
        if st.button("🧪 Spustit simulaci", use_container_width=True, key="ferm_run"):
            if not strains:
                st.warning("Vyber alespon jeden kmen")
            else:
                result = predict_ph_curve(sugar_g, temperature, starting_ph, strains, total_hours=duration_hours)
                estimated_days = estimate_completion(sugar_g, temperature, starting_ph, strains)

                st.markdown("#### Vysledky simulace")
                m1, m2, m3 = st.columns(3)
                m1.metric("Minimalni pH", f"{result['min_ph']:.2f}")
                m2.metric("Konecne pH", f"{result['final_ph']:.2f}")
                m3.metric("Rychlost fermentace", f"{result['fermentation_rate']:.2f} pH/den")

                st.info(result["status"])
                st.caption(f"⏱ Odhad dokonceni: {estimated_days} dni")

                fig = go.Figure()
                days = [h / 24 for h in result["time_points"]]
                fig.add_trace(go.Scatter(
                    x=days, y=result["ph_curve"],
                    mode="lines",
                    name="pH krivka",
                    line=dict(color="#00F2FE", width=3),
                    fill="tozeroy",
                    fillcolor="rgba(0, 242, 254, 0.1)",
                ))
                fig.add_hline(y=3.5, line_dash="dash", line_color="#22C55E",
                             annotation_text="Cilove pH (3.5)")
                fig.add_hline(y=4.5, line_dash="dot", line_color="#F59E0B",
                             annotation_text="Bezpecna zona (4.5)")
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis_title="Dny",
                    yaxis_title="pH",
                    xaxis=dict(gridcolor="#1E293B"),
                    yaxis=dict(gridcolor="#1E293B", range=[2, 7]),
                    height=400,
                    margin=dict(l=20, r=20, t=20, b=20),
                )
                st.plotly_chart(fig, use_container_width=True)

                if st.button("💾 Ulozit do deniku", key="save_ferm"):
                    db.add_fermentation_log(
                        date=datetime.now().isoformat(),
                        sugar=sugar_g, temperature=temperature,
                        ph=result["final_ph"],
                        strains=", ".join(strains),
                        duration=duration_hours,
                        notes=f"Predikce: min pH {result['min_ph']:.2f}, rate {result['fermentation_rate']:.2f}"
                    )
                    st.success("Ulozeno!")
        else:
            st.info("Nastav parametry a klikni na **Spustit simulaci**")

    with st.expander("📊 Historie fermentaci"):
        logs = db.get_fermentation_logs()
        if logs:
            df = pd.DataFrame(logs, columns=["ID", "Datum", "Cukr", "Teplota", "pH", "Kmeny", "Délka", "Poznamka"])
            st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
        else:
            st.caption("Zatim zadne zaznamy")

# ============ TAB 2: STOOL TRACKER ============
with tabs[2]:
    st.markdown("### 📋 AI Stool & Symptom Tracker")
    st.caption("Denik symptomu a Britolske skaly s korelaci na stravu a probiotika")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Novy zaznam")
        entry_date = st.date_input("Datum", value=datetime.now())
        bristol = st.select_slider(
            "Bristolska skala",
            options=list(range(1, 8)),
            value=4,
            format_func=lambda x: f"{x} - {get_bristol_description(x).split(' (')[0]}",
        )
        st.caption(get_bristol_description(bristol))

        symptoms = st.multiselect("Priznaky (dnes)", SYMPTOM_OPTIONS)
        food = st.multiselect("Jidlo (poslednich 24h)", FOOD_CATEGORIES)
        probiotics = st.multiselect("Probiotika / Fermentovane", PROBIOTIC_OPTIONS)
        notes = st.text_area("Poznamky", placeholder="Napr. pocit po jidle, energie...", max_chars=500)

        if st.button("💾 Ulozit zaznam", use_container_width=True, key="stool_save"):
            db.add_stool_log(
                date=entry_date.isoformat(),
                bristol=bristol,
                symptoms=", ".join(symptoms) if symptoms else "zadne",
                food=", ".join(food) if food else "neuvedeno",
                probiotics=", ".join(probiotics) if probiotics else "zadna",
                notes=notes or "—",
            )
            st.success("✅ Zaznam ulozen!")

    with col2:
        st.markdown("#### Analyza a trendy")
        logs = db.get_stool_logs(limit=100)
        if logs:
            analysis = analyze_correlations(logs)
            if analysis:
                m1, m2, m3 = st.columns(3)
                m1.metric("Prumer Bristol", f"{analysis['avg_bristol']:.1f}")
                m2.metric("Rozptyl", f"{analysis['std_bristol']:.2f}")
                m3.metric("Trend", analysis["trend"])

                if analysis["daily_data"]:
                    df_trend = pd.DataFrame(analysis["daily_data"])
                    fig = px.line(
                        df_trend, x="date", y="bristol",
                        markers=True,
                        title="Bristolska skala v case",
                    )
                    fig.add_hline(y=4, line_dash="dash", line_color="#22C55E", annotation_text="Ideal")
                    fig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(gridcolor="#1E293B"),
                        yaxis=dict(gridcolor="#1E293B", dtick=1),
                        height=300,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                if analysis["symptom_frequency"]:
                    st.markdown("#### Nejcastejsi priznaky")
                    sym_df = pd.DataFrame(
                        list(analysis["symptom_frequency"].items()),
                        columns=["Priznak", "Frekvence"]
                    ).head(10)
                    fig2 = px.bar(sym_df, x="Frekvence", y="Priznak", orientation="h",
                                 color="Frekvence", color_continuous_scale=["#1E293B", "#00F2FE"])
                    fig2.update_layout(template="plotly_dark", height=250, paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig2, use_container_width=True)
            else:
                st.warning("Potreba alespon 3 zaznamy pro analyzu")
        else:
            st.info("Zatim zadne zaznamy. Pridej svuj prvni!")

# ============ TAB 3: OCR SCANNER ============
with tabs[3]:
    st.markdown("### 📷 OCR Label Scanner")
    st.caption("Skener slozeni produktu s anti-sukraloza filtrem a analyzou aditiv")

    upload_method = st.radio("Zpusob vstupu", ["Nahrat obrazek", "Vlozit text slozeni"], horizontal=True)

    if upload_method == "Nahrat obrazek":
        uploaded = st.file_uploader("Nahraj fotografii slozeni", type=["png", "jpg", "jpeg", "webp"])
        if uploaded:
            with st.spinner("🔍 Analyzuji obrazek..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(uploaded.read())
                    tmp_path = tmp.name

                result = scan_label(tmp_path)
                os.unlink(tmp_path)

                if "error" in result:
                    st.error(result["error"])
                else:
                    if result["text"]:
                        with st.expander("📝 Rozpoznany text", expanded=False):
                            st.text(result["text"])
                    _display_scan_result(result)

                    db.add_scan_log(
                        date=datetime.now().isoformat(),
                        product_name="OCR Scan",
                        ingredients=result["text"][:1000],
                        flagged_additives=list(result["additives"].keys()),
                        safe=result["is_safe"],
                    )
    else:
        ingredients_text = st.text_area(
            "Vloz text slozeni",
            placeholder="Slozeni: voda, cukr, maltodextrin, sukraloza...",
            height=150,
        )
        if ingredients_text and st.button("🔍 Analyzovat text", use_container_width=True):
            from modules.study_filters import scan_additives, has_sucralose
            additives = scan_additives(ingredients_text)
            sucralose = has_sucralose(ingredients_text)
            harmful = {k: v for k, v in additives.items() if v.startswith("❌")}
            warnings = {k: v for k, v in additives.items() if v.startswith("⚠️")}
            safe_add = {k: v for k, v in additives.items() if v.startswith("✅")}
            is_safe = len(harmful) == 0

            col1, col2 = st.columns(2)
            with col1:
                if harmful:
                    st.error(f"❌ **Nevhodna aditiva ({len(harmful)})**")
                    for name, desc in harmful.items():
                        st.markdown(f"- {desc}")
                if warnings:
                    st.warning(f"⚠️ **Aditiva ke zvazeni ({len(warnings)})**")
                    for name, desc in warnings.items():
                        st.markdown(f"- {desc}")
                if safe_add:
                    st.success(f"✅ **Bezpecna aditiva ({len(safe_add)})**")
                    for name, desc in safe_add.items():
                        st.markdown(f"- {desc}")

            with col2:
                if sucralose:
                    st.error("## 🚨 SUCRALOZA DETEKOVANA!")
                    st.markdown(
                        "Sukraloza (E955) je umele sladidlo, ktere **narusuje strevni mikrobiom**, "
                        "snizuje diversitu strevnich bakterii a muze zpusobovat dysbiozu. "
                        "Pro veganskou stravu s durazem na fermentaci **durazne nedoporucujeme**."
                    )
                if is_safe:
                    st.success("✅ **Produkt je bezpecny** - zadna skodliva aditiva")
                else:
                    st.warning(f"⚠️ Produkt obsahuje {len(harmful)} problematickych aditiv")

            db.add_scan_log(
                date=datetime.now().isoformat(),
                product_name="Text vstup",
                ingredients=ingredients_text[:1000],
                flagged_additives=list(additives.keys()),
                safe=is_safe,
            )


def _display_scan_result(result):
    col1, col2 = st.columns(2)
    with col1:
        if result["harmful"]:
            st.error(f"❌ **Nevhodna aditiva ({len(result['harmful'])})**")
            for name, desc in result["harmful"].items():
                st.markdown(f"- {desc}")
        if result["warnings"]:
            st.warning(f"⚠️ **Aditiva ke zvazeni ({len(result['warnings'])})**")
            for name, desc in result["warnings"].items():
                st.markdown(f"- {desc}")
        if result["safe_additives"]:
            st.success(f"✅ **Bezpecna aditiva ({len(result['safe_additives'])})**")
            for name, desc in result["safe_additives"].items():
                st.markdown(f"- {desc}")

    with col2:
        if result["has_sucralose"]:
            st.error("## 🚨 SUCRALOZA DETEKOVANA!")
            st.markdown(
                "Sukraloza (E955) je umele sladidlo, ktere **narusuje strevni mikrobiom**, "
                "snizuje diversitu strevnich bakterii a muze zpusobovat dysbiozu. "
                "Pro veganskou stravu s durazem na fermentaci **durazne nedoporucujeme**."
            )
        if result["is_safe"]:
            st.success("✅ **Produkt je bezpecny** - zadna skodliva aditiva")
        else:
            st.warning(f"⚠️ Produkt obsahuje {len(result['harmful'])} problematickych aditiv")


with st.expander("📋 Historie skenu"):
    scans = db.get_recent_scans()
    if scans:
        for s in scans[:10]:
            flag = "❌" if not s[5] else "✅"
            st.markdown(f"{flag} **{s[2] or 'OCR Scan'}** - {s[1][:10]} | Aditiva: {s[4][:80]}")
    else:
        st.caption("Zatim zadne skeny")

# ============ TAB 4: DNA IMPORT ============
with tabs[4]:
    st.markdown("### 🧪 DNA Data Import")
    st.caption("Analyza raw dat ze sekvenacnich testu mikrobiomu (alfa/beta diverzita)")

    st.markdown("""
    <div class="sci-fi-card">
        <strong>Podporovane formaty:</strong><br>
        • CSV: sloupce <code>taxon</code>, <code>abundance</code><br>
        • FASTA: hlavicka <code>&gt;taxon</code>, nasledovana sekvenci<br>
        • <strong>Demo data</strong>: vygeneruj vzorova data pro testovani
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        upload_option = st.radio("Vstup", ["Ukazkova data", "Nahrat CSV", "Nahrat FASTA"], horizontal=True)
        dna_result = None

        if upload_option == "Ukazkova data":
            if st.button("🧬 Generovat demo data", use_container_width=True):
                dna_result = generate_sample_data()

        elif upload_option == "Nahrat CSV":
            uploaded = st.file_uploader("Nahraj CSV", type=["csv", "tsv"])
            if uploaded:
                content = uploaded.read().decode("utf-8", errors="ignore")
                dna_result = parse_csv(content)

        elif upload_option == "Nahrat FASTA":
            uploaded = st.file_uploader("Nahraj FASTA", type=["fasta", "fa", "fna", "txt"])
            if uploaded:
                content = uploaded.read().decode("utf-8", errors="ignore")
                dna_result = parse_fasta(content)

    with col2:
        if dna_result:
            if "error" in dna_result:
                st.error(dna_result["error"])
            else:
                st.markdown("#### Diverzita")
                m1, m2, m3 = st.columns(3)
                m1.metric("Shannon index", dna_result["shannon"])
                m2.metric("Simpson index", dna_result["simpson"])
                m3.metric("Pielou (evenness)", dna_result["pielou"])

                st.metric("Species", dna_result["n_species"])
                if dna_result.get("firmicutes_bacteroidetes_ratio"):
                    st.metric("F/B Ratio", dna_result["firmicutes_bacteroidetes_ratio"])

    if dna_result and "error" not in dna_result:
        st.markdown("#### 🏛️ Kmenove slozeni (Phylum)")
        phyla = dna_result["phylum_distribution"]
        if phyla:
            df_phyla = pd.DataFrame(phyla)
            fig = go.Figure(data=[
                go.Pie(
                    labels=df_phyla["phylum"],
                    values=df_phyla["relative"],
                    marker=dict(colors=df_phyla["color"]),
                    textinfo="label+percent",
                    hole=0.4,
                )
            ])
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=400,
                title="Distribuce kmenu",
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Drove slozeni")
        species = dna_result["species"]
        df_spp = pd.DataFrame(species)
        if not df_spp.empty and "relative" in df_spp.columns:
            df_spp = df_spp.sort_values("relative", ascending=False).head(20)
            fig2 = px.bar(
                df_spp, x="relative", y="taxon", orientation="h",
                color="relative", color_continuous_scale=["#1E293B", "#00F2FE"],
                title="Relativni abundance druhu",
            )
            fig2.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=max(300, len(df_spp) * 25),
                xaxis_title="Relativni abundance (%)",
            )
            st.plotly_chart(fig2, use_container_width=True)

# ============ TAB 5: ANTINUTRIENT ============
with tabs[5]:
    st.markdown("### 🌱 Antinutrient Deactivator")
    st.caption("Pruvodce pro deaktivaci fytatu, lektinu a dalsich antinutrientu")

    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.markdown("#### Vyhledat potravinu")
        food_query = st.text_input("Nazev potraviny", placeholder="Napr. cocka, mandle, quinoa...")
        if food_query:
            matches = search_food(food_query)
            if matches:
                selected_food = st.selectbox("Vyber potravinu", matches)
            else:
                st.warning("Potravina nenalezena")
                selected_food = None
        else:
            selected_food = st.selectbox("Nebo vyber ze seznamu", [""] + get_all_foods())
            if selected_food == "":
                selected_food = None

    with col2:
        if selected_food:
            info = get_food_info(selected_food)
            if info:
                st.markdown(f"#### 🥗 {selected_food}")
                ants = info["antinutrients"]
                st.markdown("##### Antinutrienty:")
                cols = st.columns(len(ants))
                for i, ant in enumerate(ants):
                    with cols[i]:
                        st.markdown(f"<div class='sci-fi-card' style='text-align:center; padding:0.5rem;'>"
                                    f"<span style='color:#EF4444; font-size:1.2rem;'>⚠️</span><br>"
                                    f"<span style='font-size:0.8rem;'>{ant}</span></div>",
                                    unsafe_allow_html=True)

                deact = info["deactivation"]
                st.markdown("##### 🛠️ Deaktivaeni protokol:")
                st.markdown(f"**Metoda:** {deact.get('metoda', 'N/A')}")

                proto_cols = st.columns(3)
                if "namaceni_hodiny" in deact:
                    proto_cols[0].metric("⏱ Namaceni", f"{deact['namaceni_hodiny']} h")
                if "namaceni_teplota" in deact:
                    proto_cols[1].metric("🌡 Teplota", deact["namaceni_teplota"])
                if "vareni_minuty" in deact:
                    proto_cols[2].metric("🔥 Vareni", f"{deact['vareni_minuty']} min")
                if "tlakovy_hrnec_min" in deact:
                    proto_cols[2].metric("⚡ Tlakovy hrnec", f"{deact['tlakovy_hrnec_min']} min")

                if deact.get("voda_vymenit"):
                    st.info("💧 **Dulezite:** Vodu po namaceni slit a vymenit!")

                if "poznamka" in deact:
                    st.warning(deact["poznamka"])

    st.markdown("<div class='divider-glow'></div>", unsafe_allow_html=True)

    st.markdown("#### 💡 Obecne tipy pro deaktivaci antinutrientu")
    tip_cols = st.columns(2)
    for i, tip in enumerate(GENERAL_TIPS):
        with tip_cols[i % 2]:
            st.markdown(f"<div class='sci-fi-card' style='padding:0.5rem;'>{tip}</div>", unsafe_allow_html=True)

# ============ TAB 6: SCIENCE DIGEST ============
with tabs[6]:
    st.markdown("### 📰 Morning Science Digest")
    st.caption("Ranni souhrn nejnovejsich vedeckych objevu z databaze")

    col1, col2 = st.columns([1, 3])

    with col1:
        st.markdown("#### 📊 Databaze")
        stats = db.get_stats()
        st.metric("Celkem studii", stats["total_studies"])

        if st.button("🔄 Vygenerovat digest", use_container_width=True, key="digest_gen"):
            with st.spinner("Analyzi nejnovejsi studie..."):
                digest = generate_digest(db, ai_client=st.session_state.gemini_model)
                st.session_state.current_digest = digest

        if st.button("📡 Rucni sync PubMed", use_container_width=True, key="manual_sync"):
            with st.spinner("Stahuji nove studie z PubMed..."):
                try:
                    added = sync_if_needed(db, force=True)
                    if added > 0:
                        st.success(f"✅ Pridano {added} novych studii")
                    else:
                        st.info("Zadne nove studie")
                except Exception as e:
                    st.error(f"Chyba: {e}")

    with col2:
        if "current_digest" in st.session_state:
            digest = st.session_state.current_digest
            st.markdown(f"#### 📰 Ranni digest ({digest['count']} studii)")
            st.markdown(f"<div class='sci-fi-card'>{digest['digest']}</div>", unsafe_allow_html=True)

            if digest.get("evidence_breakdown"):
                st.markdown("#### 📊 Rozlozeni dukazni urovne")
                ev_df = pd.DataFrame(
                    list(digest["evidence_breakdown"].items()),
                    columns=["Uroven", "Pocet"],
                )
                fig = px.pie(
                    ev_df, values="Pocet", names="Uroven",
                    color_discrete_sequence=["#22C55E", "#00F2FE", "#F59E0B", "#EF4444", "#8B5CF6"],
                )
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=300,
                )
                st.plotly_chart(fig, use_container_width=True)

            with st.expander("📚 Seznam studii"):
                for s in digest["studies"]:
                    badge = "📊" if s.get("evidence_level") in ["Meta-analysis", "RCT"] else "📋"
                    outdated = " Zastarale" if s.get("pub_date", "")[:4].isdigit() and (2026 - int(s["pub_date"][:4])) > 5 else ""
                    st.markdown(f"{badge} **{s.get('title', 'N/A')}**{outdated}")
                    st.caption(f"{s.get('authors', '')[:60]} | {s.get('journal', '')} | {s.get('pub_date', '')[:10]} | Evidence: {s.get('evidence_level', 'N/A')}")
                    st.markdown("---")
        else:
            st.info("Klikni na **Vygenerovat digest** pro vytvoreni ranniho souhrnu")

# --- Footer ---
st.markdown("<div class='divider-glow'></div>", unsafe_allow_html=True)
st.caption(
    "🧬 Symbiont.ai v1.0 | AI: Google Gemini 1.5 Flash (free) | "
    "Voice: Web Speech API | Data: PubMed | Cesky"
)
