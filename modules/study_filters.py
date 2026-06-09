import re
from datetime import datetime, timedelta


EVIDENCE_PATTERNS = [
    (r"(meta-analysis|systematic review)", "Meta-analysis"),
    (r"(randomized controlled trial|rct)", "RCT"),
    (r"(cohort study|prospective cohort)", "Cohort"),
    (r"(case-control|observational study)", "Case-Control"),
    (r"(in vitro|cell culture)", "In-vitro"),
    (r"(animal model|mouse|rat|murine)", "Animal"),
]

LATIN_PATTERN = re.compile(
    r"\b[A-Z][a-z]+ (?:[a-z]+i|oides|aceae|ales|aceae|inus|ella|oides)\b"
)

ANTINUTRIENT_KEYWORDS = {
    "phytate": "Fytát",
    "phytic acid": "Kyselina fytová",
    "lectin": "Lektin",
    "oxalate": "Oxalát",
    "tannin": "Tanin",
    "saponin": "Saponin",
    "trypsin inhibitor": "Inhibitor trypsinu",
    "protease inhibitor": "Inhibitor proteáz",
}

SUCRALOSE_PATTERNS = re.compile(
    r"(sucralose|E955|splenda|trichlorogalactosucrose)", re.IGNORECASE
)

ADDITIVE_BLACKLIST = {
    "sucralose": "❌ Sucralose (E955) - narušuje střevní mikrobiom",
    "aspartame": "⚠️ Aspartam (E951) - potenciálně negativní vliv",
    "saccharin": "⚠️ Sacharin (E954) - může ovlivnit střevní bakterie",
    "acesulfame": "⚠️ Acesulfam K (E950) - diskutabilní bezpečnost",
    "carrageenan": "⚠️ Karagenan (E407) - prozánětlivý potenciál",
    "maltodextrin": "⚠️ Maltodextrin - vysoký glykemický index",
    "titanium dioxide": "❌ Oxid titaničitý (E171) - genotoxický potenciál",
    "monosodium glutamate": "⚠️ Glutaman sodný (E621) - excitotoxin",
    "high fructose corn syrup": "❌ Kukuřičný sirup s vysokým obsahem fruktózy",
    "soy lecithin": "✅ Lecitin sójový (E322) - neutrální",
    "xanthan gum": "✅ Xanthanová guma (E415) - bezpečné",
    "guar gum": "✅ Guarová guma (E412) - bezpečné, prebiotické",
}


def filter_evidence_level(abstract):
    abstract_lower = abstract.lower()
    for pattern, level in EVIDENCE_PATTERNS:
        if re.search(pattern, abstract_lower, re.IGNORECASE):
            return level
    return "Unknown"


def extract_latin_names(text):
    return list(set(LATIN_PATTERN.findall(text)))


def is_outdated(pub_date_str):
    if not pub_date_str:
        return True
    try:
        pub_date = datetime.strptime(pub_date_str[:10], "%Y-%m-%d")
        return (datetime.now() - pub_date) > timedelta(days=365 * 5)
    except (ValueError, TypeError):
        try:
            pub_date = datetime.strptime(pub_date_str[:4], "%Y")
            return (datetime.now() - pub_date) > timedelta(days=365 * 5)
        except (ValueError, TypeError):
            return False


def detect_antinutrients(text):
    found = {}
    text_lower = text.lower()
    for eng, cze in ANTINUTRIENT_KEYWORDS.items():
        if eng in text_lower:
            found[eng] = cze
    return found


def scan_additives(text):
    flags = {}
    text_lower = text.lower()
    for additive, desc in ADDITIVE_BLACKLIST.items():
        if additive in text_lower:
            flags[additive] = desc
    return flags


def has_sucralose(text):
    return bool(SUCRALOSE_PATTERNS.search(text))
