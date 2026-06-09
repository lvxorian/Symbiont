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

from modules.config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, OPENAI_API_KEY
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
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown("""
<div class="divider-glow"></div>
""", unsafe_allow_html=True)

# --- Init ---
if "db" not in st.session_state:
    st.session_state.db = Database()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "ai_client" not in st.session_state:
    st.session_state.ai_client = None
    if DEEPSEEK_API_KEY:
        try:
            from openai import OpenAI
            st.session_state.ai_client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1"
            )
        except Exception:
            pass

if "whisper_client" not in st.session_state:
    st.session_state.whisper_client = None
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            st.session_state.whisper_client = OpenAI(api_key=OPENAI_API_KEY)
        except Exception:
            pass

db = st.session_state.db

# --- Background sync ---
if "sync_attempted" not in st.session_state:
    st.session_state.sync_attempted = True
    try:
        added = sync_if_needed(db)
        if added > 0:
            st.topper(f"📡 PubMed sync: {added} nových studií přidáno!", icon="🧬")
    except Exception as e:
        pass

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
        <h1 style="font-size: 1.8rem; margin: 0;">🧬 Symbiont.ai</h1>
        <p style="color: #94A3B8; font-size: 0.75rem; font-family: 'JetBrains Mono', monospace;">
            Autonomní AI Jarvis pro Mikrobiom
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
        st.caption("Důkazní úrovně:")
        for level, count in sorted(evidence_counts.items(), key=lambda x: x[1], reverse=True):
            icon = "📊" if level in ["Meta-analysis", "RCT"] else "📋"
            st.markdown(f"{icon} **{level}**: {count}", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("### 🎤 Hlasový vstup")
    audio_file = st.audio_input("Nahraj hlasový dotaz", label_visibility="collapsed")
    if audio_file and st.session_state.whisper_client:
        with st.spinner("Přepisuji..."):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_file.read())
                    tmp_path = tmp.name
                transcript = st.session_state.whisper_client.audio.transcriptions.create(
                    model="whisper-1", file=open(tmp_path, "rb"),
                    language="cs"
                )
                st.success(f'🎤 "{transcript.text}"')
                if "voice_input" not in st.session_state:
                    st.session_state.voice_input = transcript.text
                os.unlink(tmp_path)
            except Exception as e:
                st.error(f"Chyba přepisu: {e}")

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("### 🧪 Rychlý F2 odhad")
    quick_sugar = st.number_input("Cukr (g/l)", min_value=20, max_value=200, value=80, key="quick_sugar")
    quick_temp = st.slider("Teplota (°C)", 15, 50, 28, key="quick_temp")
    if st.button("🔬 Simulovat", key="quick_sim"):
        quick_result = predict_ph_curve(quick_sugar, quick_temp, 5.5, ["Lactobacillus plantarum"])
        st.info(f"pH za 7 dní: **{quick_result['final_ph']:.2f}** | {quick_result['status']}")

if "voice_input" in st.session_state and st.session_state.voice_input:
    voice_text = st.session_state.voice_input
    st.session_state.voice_input = None
    if voice_text not in [m["content"] for m in st.session_state.messages if m.get("role") == "user"]:
        st.session_state.messages.append({"role": "user", "content": voice_text})

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

# ============ TAB 0: AI CHAT ============
with tabs[0]:
    st.markdown("### 💬 Symbiont AI Chat")
    st.caption("Dotazuj se na mikrobiom, fermentaci, antinutrienty a vědecké studie")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Zeptej se na cokoliv o mikrobiomu..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Symbiont přemýšlí..."):
                try:
                    relevant = db.search_studies(prompt, n_results=5)
                    context = ""
                    if relevant:
                        context = "## Relevantní studie:\n"
                        for r in relevant[:5]:
                            context += f"- **{r['title']}** ({r['evidence_level']}, {r['pub_date']})\n"
                        context += "\n"

                    full_prompt = f"""Jsi Symbiont.ai, autonomní AI asistent specializovaný na střevní mikrobiom, 
fermentaci, rostlinnou výživu a medicinální houby. Uživatel je striktní vegan (14 let), 
zajímá se o F2 fermentaci, trávení rostlinných bílkovin a eliminaci antinutrientů.

Používej vědecké poznatky, latinskou nomenklaturu pro bakterie, a odkazuj na úroveň důkazů.
Odpovídej česky, srozumitelně a prakticky.

{context}
Uživatel: {prompt}"""

                    if st.session_state.ai_client:
                        response = st.session_state.ai_client.chat.completions.create(
                            model=DEEPSEEK_MODEL,
                            messages=[
                                {"role": "system", "content": "Jsi expert na mikrobiom. Odpovídej česky, věcně, s odkazy na studie."},
                                {"role": "user", "content": full_prompt},
                            ],
                            temperature=0.3,
                            max_tokens=2000,
                        )
                        reply = response.choices[0].message.content
                    else:
                        reply = "⚠️ API klíč pro DeepSeek není nastaven. Zkopíruj `.env.template` na `.env` a doplň `DEEPSEEK_API_KEY`."

                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

                    if relevant:
                        with st.expander("📚 Zdroje z databáze"):
                            for r in relevant[:5]:
                                badge = "📊" if r["evidence_level"] in ["RCT", "Meta-analysis"] else "📋"
                                st.markdown(f"{badge} **{r['title']}**")
                                st.caption(f"Evidence: {r['evidence_level']} | {r['pub_date']}")
                                st.markdown(f"[Otevřít]({r['url']})")
                                st.markdown("---")

                except Exception as e:
                    st.error(f"❌ Chyba: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": f"❌ Chyba: {e}"})

    if st.button("🗑 Smazat konverzaci", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()

# ============ TAB 1: F2 FERMENTATION ============
with tabs[1]:
    st.markdown("### 🧬 F2 Fermentation Simulator")
    st.caption("Modelování druhé fáze kvašení (kombucha/tibi) - predikce pH křivky")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Vstupní parametry")
        sugar_type = st.selectbox("Typ cukru", get_sugar_types())
        sugar_g = st.slider("Množství cukru (g/l)", 20, 200, 80)
        temperature = st.slider("Teplota kvašení (°C)", 15, 50, 28)
        starting_ph = st.slider("Počáteční pH", 3.5, 7.0, 5.5, 0.1)
        strains = st.multiselect(
            "Mikrobiální kmeny",
            get_available_strains(),
            default=["Lactobacillus plantarum", "SCOBY (kombucha)"],
        )
        duration_days = st.slider("Délka fermentace (dny)", 1, 30, 7)
        duration_hours = duration_days * 24

    with col2:
        if st.button("🧪 Spustit simulaci", use_container_width=True, key="ferm_run"):
            if not strains:
                st.warning("Vyber alespoň jeden kmen")
            else:
                result = predict_ph_curve(sugar_g, temperature, starting_ph, strains, total_hours=duration_hours)
                estimated_days = estimate_completion(sugar_g, temperature, starting_ph, strains)

                st.markdown("#### Výsledky simulace")
                m1, m2, m3 = st.columns(3)
                m1.metric("Minimální pH", f"{result['min_ph']:.2f}")
                m2.metric("Konečné pH", f"{result['final_ph']:.2f}")
                m3.metric("Rychlost fermentace", f"{result['fermentation_rate']:.2f} pH/den")

                st.info(result["status"])
                st.caption(f"⏱ Odhad dokončení: {estimated_days} dní")

                fig = go.Figure()
                days = [h / 24 for h in result["time_points"]]
                fig.add_trace(go.Scatter(
                    x=days, y=result["ph_curve"],
                    mode="lines",
                    name="pH křivka",
                    line=dict(color="#00F2FE", width=3),
                    fill="tozeroy",
                    fillcolor="rgba(0, 242, 254, 0.1)",
                ))
                fig.add_hline(y=3.5, line_dash="dash", line_color="#22C55E",
                             annotation_text="Cílové pH (3.5)")
                fig.add_hline(y=4.5, line_dash="dot", line_color="#F59E0B",
                             annotation_text="Bezpečná zóna (4.5)")
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

                if st.button("💾 Uložit do deníku", key="save_ferm"):
                    db.add_fermentation_log(
                        date=datetime.now().isoformat(),
                        sugar=sugar_g, temperature=temperature,
                        ph=result["final_ph"],
                        strains=", ".join(strains),
                        duration=duration_hours,
                        notes=f"Predikce: min pH {result['min_ph']:.2f}, rate {result['fermentation_rate']:.2f}"
                    )
                    st.success("Uloženo!")
        else:
            st.info("Nastav parametry a klikni na **Spustit simulaci**")

    with st.expander("📊 Historie fermentací"):
        logs = db.get_fermentation_logs()
        if logs:
            df = pd.DataFrame(logs, columns=["ID", "Datum", "Cukr", "Teplota", "pH", "Kmeny", "Délka", "Poznámka"])
            st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
        else:
            st.caption("Zatím žádné záznamy")

# ============ TAB 2: STOOL TRACKER ============
with tabs[2]:
    st.markdown("### 📋 AI Stool & Symptom Tracker")
    st.caption("Deník symptomů a Bristolské škály s korelací na stravu a probiotika")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Nový záznam")
        entry_date = st.date_input("Datum", value=datetime.now())
        bristol = st.select_slider(
            "Bristolská škála",
            options=list(range(1, 8)),
            value=4,
            format_func=lambda x: f"{x} - {get_bristol_description(x).split(' (')[0]}",
        )
        st.caption(get_bristol_description(bristol))

        symptoms = st.multiselect("Příznaky (dnes)", SYMPTOM_OPTIONS)
        food = st.multiselect("Jídlo (posledních 24h)", FOOD_CATEGORIES)
        probiotics = st.multiselect("Probiotika / Fermentované", PROBIOTIC_OPTIONS)
        notes = st.text_area("Poznámky", placeholder="Např. pocit po jídle, energie...", max_chars=500)

        if st.button("💾 Uložit záznam", use_container_width=True, key="stool_save"):
            db.add_stool_log(
                date=entry_date.isoformat(),
                bristol=bristol,
                symptoms=", ".join(symptoms) if symptoms else "žádné",
                food=", ".join(food) if food else "neuvedeno",
                probiotics=", ".join(probiotics) if probiotics else "žádná",
                notes=notes or "—",
            )
            st.success("✅ Záznam uložen!")

    with col2:
        st.markdown("#### Analýza a trendy")
        logs = db.get_stool_logs(limit=100)
        if logs:
            analysis = analyze_correlations(logs)
            if analysis:
                m1, m2, m3 = st.columns(3)
                m1.metric("Průměr Bristol", f"{analysis['avg_bristol']:.1f}")
                m2.metric("Rozptyl", f"{analysis['std_bristol']:.2f}")
                m3.metric("Trend", analysis["trend"])

                if analysis["daily_data"]:
                    df_trend = pd.DataFrame(analysis["daily_data"])
                    fig = px.line(
                        df_trend, x="date", y="bristol",
                        markers=True,
                        title="Bristolská škála v čase",
                    )
                    fig.add_hline(y=4, line_dash="dash", line_color="#22C55E", annotation_text="Ideál")
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
                    st.markdown("#### Nejčastější příznaky")
                    sym_df = pd.DataFrame(
                        list(analysis["symptom_frequency"].items()),
                        columns=["Příznak", "Frekvence"]
                    ).head(10)
                    fig2 = px.bar(sym_df, x="Frekvence", y="Příznak", orientation="h",
                                 color="Frekvence", color_continuous_scale=["#1E293B", "#00F2FE"])
                    fig2.update_layout(template="plotly_dark", height=250, paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig2, use_container_width=True)
            else:
                st.warning("Potřeba alespoň 3 záznamy pro analýzu")
        else:
            st.info("Zatím žádné záznamy. Přidej svůj první!")

# ============ TAB 3: OCR SCANNER ============
with tabs[3]:
    st.markdown("### 📷 OCR Label Scanner")
    st.caption("Skener složení produktů s anti-sukralóza filtrem a analýzou aditiv")

    upload_method = st.radio("Způsob vstupu", ["Nahrát obrázek", "Vložit text složení"], horizontal=True)

    if upload_method == "Nahrát obrázek":
        uploaded = st.file_uploader("Nahraj fotografii složení", type=["png", "jpg", "jpeg", "webp"])
        if uploaded:
            with st.spinner("🔍 Analyzuji obrázek..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(uploaded.read())
                    tmp_path = tmp.name

                result = scan_label(tmp_path)
                os.unlink(tmp_path)

                if "error" in result:
                    st.error(result["error"])
                else:
                    if result["text"]:
                        with st.expander("📝 Rozpoznaný text", expanded=False):
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
            "Vlož text složení",
            placeholder="Složení: voda, cukr, maltodextrin, sukralóza...",
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
                    st.error(f"❌ **Nevhodná aditiva ({len(harmful)})**")
                    for name, desc in harmful.items():
                        st.markdown(f"- {desc}")
                if warnings:
                    st.warning(f"⚠️ **Aditiva ke zvážení ({len(warnings)})**")
                    for name, desc in warnings.items():
                        st.markdown(f"- {desc}")
                if safe_add:
                    st.success(f"✅ **Bezpečná aditiva ({len(safe_add)})**")
                    for name, desc in safe_add.items():
                        st.markdown(f"- {desc}")

            with col2:
                if sucralose:
                    st.error("## 🚨 SUCRALÓZA DETEKOVÁNA!")
                    st.markdown(
                        "Sukralóza (E955) je umělé sladidlo, které **narušuje střevní mikrobiom**, "
                        "snižuje diversitu střevních bakterií a může způsobovat dysbiózu. "
                        "Pro veganskou stravu s důrazem na fermentaci **důrazně nedoporučujeme**."
                    )
                if is_safe:
                    st.success("✅ **Produkt je bezpečný** - žádná škodlivá aditiva")
                else:
                    st.warning(f"⚠️ Produkt obsahuje {len(harmful)} problematických aditiv")

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
            st.error(f"❌ **Nevhodná aditiva ({len(result['harmful'])})**")
            for name, desc in result["harmful"].items():
                st.markdown(f"- {desc}")
        if result["warnings"]:
            st.warning(f"⚠️ **Aditiva ke zvážení ({len(result['warnings'])})**")
            for name, desc in result["warnings"].items():
                st.markdown(f"- {desc}")
        if result["safe_additives"]:
            st.success(f"✅ **Bezpečná aditiva ({len(result['safe_additives'])})**")
            for name, desc in result["safe_additives"].items():
                st.markdown(f"- {desc}")

    with col2:
        if result["has_sucralose"]:
            st.error("## 🚨 SUCRALÓZA DETEKOVÁNA!")
            st.markdown(
                "Sukralóza (E955) je umělé sladidlo, které **narušuje střevní mikrobiom**, "
                "snižuje diversitu střevních bakterií a může způsobovat dysbiózu. "
                "Pro veganskou stravu s důrazem na fermentaci **důrazně nedoporučujeme**."
            )
        if result["is_safe"]:
            st.success("✅ **Produkt je bezpečný** - žádná škodlivá aditiva")
        else:
            st.warning(f"⚠️ Produkt obsahuje {len(result['harmful'])} problematických aditiv")

with st.expander("📋 Historie skenů"):
    scans = db.get_recent_scans()
    if scans:
        for s in scans[:10]:
            flag = "❌" if not s[5] else "✅"
            st.markdown(f"{flag} **{s[2] or 'OCR Scan'}** - {s[1][:10]} | Aditiva: {s[4][:80]}")
    else:
        st.caption("Zatím žádné skeny")

# ============ TAB 4: DNA IMPORT ============
with tabs[4]:
    st.markdown("### 🧪 DNA Data Import")
    st.caption("Analýza raw dat ze sekvenačních testů mikrobiomu (α/β diverzita)")

    st.markdown("""
    <div class="sci-fi-card">
        <strong>Podporované formáty:</strong><br>
        • CSV: sloupce <code>taxon</code>, <code>abundance</code><br>
        • FASTA: hlavička <code>&gt;taxon</code>, následovaná sekvencí<br>
        • <strong>Demo data</strong>: vygeneruj vzorová data pro testování
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        upload_option = st.radio("Vstup", ["Ukázková data", "Nahrát CSV", "Nahrát FASTA"], horizontal=True)
        dna_result = None

        if upload_option == "Ukázková data":
            if st.button("🧬 Generovat demo data", use_container_width=True):
                dna_result = generate_sample_data()

        elif upload_option == "Nahrát CSV":
            uploaded = st.file_uploader("Nahraj CSV", type=["csv", "tsv"])
            if uploaded:
                content = uploaded.read().decode("utf-8", errors="ignore")
                dna_result = parse_csv(content)

        elif upload_option == "Nahrát FASTA":
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
        st.markdown("#### 🏛️ Kmenové složení (Phylum)")
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
                title="Distribuce kmenů",
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Druhové složení")
        species = dna_result["species"]
        df_spp = pd.DataFrame(species)
        if not df_spp.empty and "relative" in df_spp.columns:
            df_spp = df_spp.sort_values("relative", ascending=False).head(20)
            fig2 = px.bar(
                df_spp, x="relative", y="taxon", orientation="h",
                color="relative", color_continuous_scale=["#1E293B", "#00F2FE"],
                title="Relativní abundance druhů",
            )
            fig2.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=max(300, len(df_spp) * 25),
                xaxis_title="Relativní abundance (%)",
            )
            st.plotly_chart(fig2, use_container_width=True)

# ============ TAB 5: ANTINUTRIENT ============
with tabs[5]:
    st.markdown("### 🌱 Antinutrient Deactivator")
    st.caption("Průvodce pro deaktivaci fytátů, lektinů a dalších antinutrientů")

    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.markdown("#### Vyhledat potravinu")
        food_query = st.text_input("Název potraviny", placeholder="Např. čočka, mandle, quinoa...")
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
                st.markdown("##### 🛠️ Deaktivační protokol:")
                st.markdown(f"**Metoda:** {deact.get('metoda', 'N/A')}")

                proto_cols = st.columns(3)
                if "namaceni_hodiny" in deact:
                    proto_cols[0].metric("⏱ Namáčení", f"{deact['namaceni_hodiny']} h")
                if "namaceni_teplota" in deact:
                    proto_cols[1].metric("🌡 Teplota", deact["namaceni_teplota"])
                if "vareni_minuty" in deact:
                    proto_cols[2].metric("🔥 Vaření", f"{deact['vareni_minuty']} min")
                if "tlakovy_hrnec_min" in deact:
                    proto_cols[2].metric("⚡ Tlakový hrnec", f"{deact['tlakovy_hrnec_min']} min")

                if deact.get("voda_vymenit"):
                    st.info("💧 **Důležité:** Vodu po namáčení slít a vyměnit!")

                if "poznamka" in deact:
                    st.warning(deact["poznamka"])

    st.markdown("<div class='divider-glow'></div>", unsafe_allow_html=True)

    st.markdown("#### 💡 Obecné tipy pro deaktivaci antinutrientů")
    tip_cols = st.columns(2)
    for i, tip in enumerate(GENERAL_TIPS):
        with tip_cols[i % 2]:
            st.markdown(f"<div class='sci-fi-card' style='padding:0.5rem;'>{tip}</div>", unsafe_allow_html=True)

# ============ TAB 6: SCIENCE DIGEST ============
with tabs[6]:
    st.markdown("### 📰 Morning Science Digest")
    st.caption("Ranní souhrn nejnovějších vědeckých objevů z databáze")

    col1, col2 = st.columns([1, 3])

    with col1:
        st.markdown("#### 📊 Databáze")
        stats = db.get_stats()
        st.metric("Celkem studií", stats["total_studies"])

        if st.button("🔄 Vygenerovat digest", use_container_width=True, key="digest_gen"):
            with st.spinner("Analyzuji nejnovější studie..."):
                digest = generate_digest(db, ai_client=st.session_state.ai_client)
                st.session_state.current_digest = digest

        if st.button("📡 Ruční sync PubMed", use_container_width=True, key="manual_sync"):
            with st.spinner("Stahuji nové studie z PubMed..."):
                try:
                    added = sync_if_needed(db, force=True)
                    if added > 0:
                        st.success(f"✅ Přidáno {added} nových studií")
                    else:
                        st.info("Žádné nové studie")
                except Exception as e:
                    st.error(f"Chyba: {e}")

    with col2:
        if "current_digest" in st.session_state:
            digest = st.session_state.current_digest
            st.markdown(f"#### 📰 Ranní digest ({digest['count']} studií)")
            st.markdown(f"<div class='sci-fi-card'>{digest['digest']}</div>", unsafe_allow_html=True)

            if digest.get("evidence_breakdown"):
                st.markdown("#### 📊 Rozložení důkazní úrovně")
                ev_df = pd.DataFrame(
                    list(digest["evidence_breakdown"].items()),
                    columns=["Úroveň", "Počet"],
                )
                fig = px.pie(
                    ev_df, values="Počet", names="Úroveň",
                    color_discrete_sequence=["#22C55E", "#00F2FE", "#F59E0B", "#EF4444", "#8B5CF6"],
                )
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=300,
                )
                st.plotly_chart(fig, use_container_width=True)

            with st.expander("📚 Seznam studií"):
                for s in digest["studies"]:
                    badge = "📊" if s.get("evidence_level") in ["Meta-analysis", "RCT"] else "📋"
                    outdated = " ⚠️ Zastaralé" if s.get("pub_date", "")[:4].isdigit() and (2026 - int(s["pub_date"][:4])) > 5 else ""
                    st.markdown(f"{badge} **{s.get('title', 'N/A')}**{outdated}")
                    st.caption(f"{s.get('authors', '')[:60]} | {s.get('journal', '')} | {s.get('pub_date', '')[:10]} | Evidence: {s.get('evidence_level', 'N/A')}")
                    st.markdown("---")
        else:
            st.info("Klikni na **Vygenerovat digest** pro vytvoření ranního souhrnu")

# --- Footer ---
st.markdown("<div class='divider-glow'></div>", unsafe_allow_html=True)
st.caption(
    "🧬 Symbiont.ai v1.0 | Data z PubMed | AI engine: DeepSeek-Flash-v4 | "
    "Vytvořeno pro veganskou mikrobiomovou optimalizaci"
)
