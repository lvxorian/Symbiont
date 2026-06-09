import numpy as np
from datetime import datetime

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


def predict_ph_curve(sugar_g, temperature, starting_ph, strains, total_hours=168, points=100):
    if not strains:
        strains = list(STRAIN_PARAMS.keys())[:1]

    time_points = np.linspace(0, total_hours, points)
    ph_curve = np.full_like(time_points, starting_ph, dtype=float)

    for strain_name in strains:
        params = STRAIN_PARAMS.get(strain_name, STRAIN_PARAMS["Lactobacillus plantarum"])
        temp_factor = _temp_factor(temperature, params)
        sugar_factor = sugar_g / 100.0
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
