FOOD_DB = {
    "Čočka": {
        "antinutrients": ["Fytát", "Lektin", "Inhibitor trypsinu"],
        "deactivation": {
            "metoda": "Namáčení + vaření",
            "namaceni_hodiny": 8,
            "namaceni_teplota": "Pokojová",
            "voda_vymenit": True,
            "vareni_minuty": 20,
            "tlakovy_hrnec_min": 10,
            "poznamka": "Slévání vody po namáčení výrazně snižuje fytáty",
        },
    },
    "Cizrna": {
        "antinutrients": ["Fytát", "Lektin", "Saponin"],
        "deactivation": {
            "metoda": "Namáčení + vaření",
            "namaceni_hodiny": 10,
            "namaceni_teplota": "Pokojová",
            "voda_vymenit": True,
            "vareni_minuty": 60,
            "tlakovy_hrnec_min": 20,
            "poznamka": "Fermentace (tempeh) snižuje fytáty o 70-80%",
        },
    },
    "Fazole červené": {
        "antinutrients": ["Lektin (fytohemaglutinin)", "Fytát", "Inhibitor trypsinu"],
        "deactivation": {
            "metoda": "Namáčení + důkladné vaření",
            "namaceni_hodiny": 12,
            "namaceni_teplota": "Pokojová",
            "voda_vymenit": True,
            "vareni_minuty": 30,
            "tlakovy_hrnec_min": 15,
            "poznamka": "⚠️ NEDOSTATEČNÉ VAŘENÍ MŮŽE ZPŮSOBIT OTRAVU! Lektin se deaktivuje až při 100°C po 30 min.",
        },
    },
    "Fazole černé": {
        "antinutrients": ["Fytát", "Lektin", "Tanin"],
        "deactivation": {
            "metoda": "Namáčení + vaření",
            "namaceni_hodiny": 8,
            "namaceni_teplota": "Pokojová",
            "voda_vymenit": True,
            "vareni_minuty": 45,
            "tlakovy_hrnec_min": 15,
            "poznamka": "Klíčení snižuje fytáty o 40-60%",
        },
    },
    "Mungo fazole": {
        "antinutrients": ["Fytát", "Lektin"],
        "deactivation": {
            "metoda": "Klíčení nebo vaření",
            "namaceni_hodiny": 6,
            "namaceni_teplota": "Pokojová",
            "voda_vymenit": True,
            "vareni_minuty": 20,
            "tlakovy_hrnec_min": 8,
            "poznamka": "Ideální na klíčení - výrazné snížení antinutrientů",
        },
    },
    "Hrách": {
        "antinutrients": ["Fytát", "Inhibitor trypsinu", "Lektin"],
        "deactivation": {
            "metoda": "Namáčení + vaření",
            "namaceni_hodiny": 6,
            "namaceni_teplota": "Pokojová",
            "voda_vymenit": False,
            "vareni_minuty": 40,
            "tlakovy_hrnec_min": 12,
            "poznamka": "Fermentace výrazně zlepšuje stravitelnost",
        },
    },
    "Mandle": {
        "antinutrients": ["Fytát", "Oxalát", "Inhibitor trypsinu"],
        "deactivation": {
            "metoda": "Namáčení",
            "namaceni_hodiny": 12,
            "namaceni_teplota": "Pokojová nebo lednice",
            "voda_vymenit": True,
            "poznamka": "Po namáčení sloupnout slupku. Až 50% snížení fytátů.",
        },
    },
    "Vlašské ořechy": {
        "antinutrients": ["Fytát", "Tanin", "Oxalát"],
        "deactivation": {
            "metoda": "Namáčení",
            "namaceni_hodiny": 8,
            "namaceni_teplota": "Pokojová",
            "voda_vymenit": True,
            "poznamka": "Mírné pražení (150°C, 10min) snižuje taniny",
        },
    },
    "Kešu": {
        "antinutrients": ["Fytát", "Lektin"],
        "deactivation": {
            "metoda": "Namáčení",
            "namaceni_hodiny": 4,
            "namaceni_teplota": "Pokojová",
            "voda_vymenit": True,
            "poznamka": "Kešu obsahuje méně antinutrientů než jiné ořechy",
        },
    },
    "Špenát": {
        "antinutrients": ["Oxalát", "Fytát"],
        "deactivation": {
            "metoda": "Vaření v páře / blanšírování",
            "vareni_minuty": 3,
            "poznamka": "Vaření v páře snižuje oxaláty o 30-50%. Vodu nevylévat - oxaláty jsou ve vodě.",
        },
    },
    "Quinoa": {
        "antinutrients": ["Saponin", "Fytát"],
        "deactivation": {
            "metoda": "Důkladné propláchnutí + namáčení",
            "namaceni_hodiny": 4,
            "namaceni_teplota": "Pokojová",
            "voda_vymenit": True,
            "poznamka": "Saponiny se odstraní propláchnutím - quinoa by měla přestat pěnit",
        },
    },
    "Oves": {
        "antinutrients": ["Fytát"],
        "deactivation": {
            "metoda": "Namáčení přes noc",
            "namaceni_hodiny": 12,
            "namaceni_teplota": "Lednice",
            "voda_vymenit": False,
            "poznamka": "Overnight oats - kyselé prostředí (citron/jablečný ocet) aktivuje fytázu",
        },
    },
    "Tofu": {
        "antinutrients": ["Fytát", "Inhibitor trypsinu"],
        "deactivation": {
            "metoda": "Vaření (výroba tofu již zahrnuje vaření)",
            "poznamka": "Průmyslové tofu je již ošetřeno. Doporučuje se grilování nebo smažení pro lepší stravitelnost.",
        },
    },
    "Tempeh": {
        "antinutrients": ["Fytát"],
        "deactivation": {
            "metoda": "Fermentace (součást výroby)",
            "poznamka": "✅ Fermentace snižuje fytáty o 70-80%. Tempeh je jednou z nejlépe stravitelných forem luštěnin.",
        },
    },
}


GENERAL_TIPS = [
    "🌱 Namáčení přes noc výrazně snižuje obsah fytátů a lektinů",
    "💧 Slévání namáčecí vody je kritické - odstraňuje se tím většina antinutrientů",
    "🔥 Tlakový hrnec je nejefektivnější způsob deaktivace lektinů",
    "🧪 Přidání citronové šťávy nebo jablečného octa do namáčecí vody aktivuje fytázu",
    "⏱ Klíčení (24-48h) snižuje fytáty o 40-80% v závislosti na druhu",
    "🫘 Fermentace je nejúčinnější metoda - snižuje všechny typy antinutrientů",
    "🌡 Vaření při 100°C po dobu 20-30 minut deaktivuje většinu lektinů",
    "🥛 Kombinace s vitaminem C zlepšuje vstřebávání železa i přes přítomnost fytátů",
]


def get_food_info(name):
    return FOOD_DB.get(name)


def get_all_foods():
    return list(FOOD_DB.keys())


def search_food(query):
    query = query.lower()
    return [name for name in FOOD_DB if query in name.lower()]
