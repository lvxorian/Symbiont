import numpy as np
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

STRAIN_PARAMS = {
    "Lactobacillus plantarum": {"temp_min": 15, "temp_max": 45, "opt_temp": 30, "acid_prod": 1.0},
    "Saccharomyces boulardii": {"temp_min": 20, "temp_max": 37, "opt_temp": 30, "acid_prod": 0.3},
    "SCOBY (kombucha)": {"temp_min": 20, "temp_max": 35, "opt_temp": 28, "acid_prod": 0.7},
    "Tibi (vodní kefír)": {"temp_min": 18, "temp_max": 32, "opt_temp": 25, "acid_prod": 0.6},
    "Bifidobacterium bifidum": {"temp_min": 30, "temp_max": 40, "opt_temp": 37, "acid_prod": 0.9},
    "Lactobacillus reuteri": {"temp_min": 25, "temp_max": 42, "opt_temp": 37, "acid_prod": 1.1},
}

SUGAR_TYPES = {
    "Bílý cukr": 1.0,
    "Třtinový cukr": 0.95,
    "Med": 1.15,
    "Javorový sirup": 0.85,
    "Kokosový cukr": 0.80,
    "Agávový sirup": 0.90,
}


def predict_ph_curve(sugar_g, temperature, starting_ph, strains, sugar_type=None, total_hours=168, points=100):
    if not strains:
        strains = list(STRAIN_PARAMS.keys())[:1]

    time_points = np.linspace(0, total_hours, points)
    ph_curve = np.full_like(time_points, starting_ph, dtype=float)

    sugar_mult = SUGAR_TYPES.get(sugar_type, 1.0) if sugar_type else 1.0

    for strain_name in strains:
        params = STRAIN_PARAMS.get(strain_name, STRAIN_PARAMS["Lactobacillus plantarum"])
        temp_factor = _temp_factor(temperature, params)
        sugar_factor = (sugar_g / 100.0) * sugar_mult
        strain_count = len(strains)

        acid_prod = params["acid_prod"] * temp_factor * sugar_factor / strain_count
        lag_phase = 12 if strain_name in ["SCOBY (kombucha)", "Tibi (vodní kefír)"] else 4

        for i, t in enumerate(time_points):
            if t < lag_phase:
                continue
            growth = 1 - np.exp(-(t - lag_phase) / (48 / strain_count))
            ph_drop = acid_prod * growth * 0.15
            current_ph = starting_ph - ph_drop
            ph_curve[i] = min(ph_curve[i], max(current_ph, 2.5))

    min_ph = float(np.min(ph_curve))
    final_ph = float(ph_curve[-1])
    fermentation_rate = float((starting_ph - final_ph) / (total_hours / 24))

    if final_ph < 3.5:
        status = "✅ Hotovo - pH v cílovém rozmezí"
    elif final_ph < 4.0:
        status = "⚠️ Téměř hotovo - sledujte pH"
    elif final_ph < 4.5:
        status = "🔄 Aktivní fermentace - pokračujte"
    else:
        status = "⏳ Počáteční fáze - zatím čekejte"

    return {
        "time_points": time_points.tolist(),
        "ph_curve": ph_curve.tolist(),
        "min_ph": min_ph,
        "final_ph": final_ph,
        "fermentation_rate": fermentation_rate,
        "status": status,
        "total_hours": total_hours,
    }


def _temp_factor(temperature, params):
    if temperature < params["temp_min"] or temperature > params["temp_max"]:
        return 0.1
    opt = params["opt_temp"]
    diff = abs(temperature - opt)
    return max(0.1, 1.0 - diff / (opt - params["temp_min"]))


def estimate_completion(sugar_g, temperature, starting_ph, strains):
    result = predict_ph_curve(sugar_g, temperature, starting_ph, strains)
    half_idx = len(result["time_points"]) // 2
    mid_ph = result["ph_curve"][half_idx]
    drop_rate = (starting_ph - mid_ph) / (result["total_hours"] / 2 / 24)
    remaining_drop = (mid_ph - 3.2)
    if drop_rate > 0:
        estimated_days = remaining_drop / drop_rate
    else:
        estimated_days = 7
    return max(1, min(30, round(estimated_days)))


def get_available_strains():
    return list(STRAIN_PARAMS.keys())


def get_sugar_types():
    return list(SUGAR_TYPES.keys())


def render_fermentation(db):
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
                r = predict_ph_curve(sugar_g, temperature, starting_ph, strains, sugar_type=sugar_type, total_hours=days*24)
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
