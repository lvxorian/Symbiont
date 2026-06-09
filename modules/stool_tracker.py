import pandas as pd
import numpy as np
from datetime import datetime

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
