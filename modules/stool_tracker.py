import pandas as pd
import numpy as np
from datetime import datetime

import streamlit as st
import plotly.express as px

BRISTOL_DESCRIPTIONS = {
    1: "Oddělené tvrdé kuličky (těžká zácpa)",
    2: "Hrudkovitá klobása (mírná zácpa)",
    3: "Klobása s prasklinami (normální)",
    4: "Hladká hadovitá stolice (normální)",
    5: "Měkké oddělené kousky (nedostatek vlákniny)",
    6: "Kašovitá stolice (mírný průjem)",
    7: "Vodnatá stolice (těžký průjem)",
}

SYMPTOM_OPTIONS = [
    "Nadýmání", "Plynatost", "Křeče", "Pálení žáhy",
    "Únava po jídle", "Nevolnost", "Bolest břicha",
    "Akné", "Joint pain", "Brain fog", "Úzkost",
    "Nekvalitní spánek", "Svědění kůže",
]

PROBIOTIC_OPTIONS = [
    "Lactobacillus rhamnosus GG", "Bifidobacterium lactis BB-12",
    "Saccharomyces boulardii", "Lactobacillus plantarum 299v",
    "Bifidobacterium longum 35624", "Kombucha", "Tibi kefír",
    "Kysané zelí", "Kimchi", "Tempeh",
]

FOOD_CATEGORIES = [
    "Luštěniny", "Ořechy", "Semínka", "Celozrnné obiloviny",
    "Ovoce", "Zelenina", "Fermentované potraviny",
    "Medicínální houby", "Rostlinné bílkoviny (tofu/tempeh/seitan)",
    "Zpracované veganské produkty",
]


def analyze_correlations(stool_logs):
    if not stool_logs or len(stool_logs) < 3:
        return None

    df = pd.DataFrame(stool_logs, columns=["id", "date", "bristol", "symptoms", "food", "probiotics", "notes"])
    df["bristol"] = pd.to_numeric(df["bristol"], errors="coerce")
    df = df.dropna(subset=["bristol"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if df.empty or len(df) < 3:
        return None

    avg_bristol = float(df["bristol"].mean())
    std_bristol = float(df["bristol"].std())
    min_bristol = int(df["bristol"].min())
    max_bristol = int(df["bristol"].max())
    trend = _calculate_trend(df["bristol"].tolist())

    symptom_freq = {}
    for s in df["symptoms"].dropna():
        for sym in str(s).split(","):
            sym = sym.strip()
            if sym:
                symptom_freq[sym] = symptom_freq.get(sym, 0) + 1

    food_freq = {}
    for f in df["food"].dropna():
        for item in str(f).split(","):
            item = item.strip()
            if item:
                food_freq[item] = food_freq.get(item, 0) + 1

    return {
        "avg_bristol": avg_bristol,
        "std_bristol": std_bristol,
        "min_bristol": min_bristol,
        "max_bristol": max_bristol,
        "trend": trend,
        "symptom_frequency": dict(sorted(symptom_freq.items(), key=lambda x: x[1], reverse=True)),
        "food_frequency": dict(sorted(food_freq.items(), key=lambda x: x[1], reverse=True)),
        "total_entries": len(df),
        "daily_data": [{"date": str(r["date"].date()), "bristol": r["bristol"]} for _, r in df.iterrows()],
    }


def _calculate_trend(values):
    if len(values) < 2:
        return "stabilní"
    x = np.arange(len(values))
    y = np.array(values)
    if np.std(x) == 0:
        return "stabilní"
    slope = np.polyfit(x, y, 1)[0]
    if slope > 0.1:
        return "stoupající (zlepšení)"
    elif slope < -0.1:
        return "klesající (zhoršení)"
    return "stabilní"


def get_bristol_description(score):
    return BRISTOL_DESCRIPTIONS.get(score, "Neznámá hodnota")


def render_stool_tracker(db):
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
                if a.get("symptom_frequency"):
                    st.markdown("#### Příznaky")
                    for sym, count in list(a["symptom_frequency"].items())[:5]:
                        st.markdown(f"- {sym}: **{count}x**")
                if a.get("food_frequency"):
                    st.markdown("#### Nejčastější jídla")
                    for item, count in list(a["food_frequency"].items())[:5]:
                        st.markdown(f"- {item}: **{count}x**")
            else:
                st.warning("Potreba 3+ zaznamu pro analyzu")
