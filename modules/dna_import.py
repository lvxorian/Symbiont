import pandas as pd
import numpy as np
import re
from io import StringIO


PHYLA_COLORS = {
    "Firmicutes": "#00F2FE",
    "Bacteroidetes": "#22C55E",
    "Actinobacteria": "#F59E0B",
    "Proteobacteria": "#EF4444",
    "Verrucomicrobia": "#8B5CF6",
    "Other": "#6B7280",
}

KNOWN_GENERA = {
    "Lactobacillus": "Firmicutes",
    "Bifidobacterium": "Actinobacteria",
    "Akkermansia": "Verrucomicrobia",
    "Faecalibacterium": "Firmicutes",
    "Prevotella": "Bacteroidetes",
    "Bacteroides": "Bacteroidetes",
    "Roseburia": "Firmicutes",
    "Eubacterium": "Firmicutes",
    "Ruminococcus": "Firmicutes",
    "Clostridium": "Firmicutes",
    "Escherichia": "Proteobacteria",
    "Klebsiella": "Proteobacteria",
    "Salmonella": "Proteobacteria",
    "Streptococcus": "Firmicutes",
    "Enterococcus": "Firmicutes",
    "Methanobrevibacter": "Other",
}


def parse_csv(content):
    try:
        df = pd.read_csv(StringIO(content))
    except Exception as e:
        return {"error": f"Chyba parsování CSV: {e}"}

    if "taxon" in df.columns and "abundance" in df.columns:
        pass
    elif df.shape[1] >= 2:
        df.columns = ["taxon", "abundance"] + list(df.columns[2:])
    else:
        return {"error": "CSV musí mít sloupce 'taxon' a 'abundance'"}

    df["abundance"] = pd.to_numeric(df["abundance"], errors="coerce")
    df = df.dropna(subset=["abundance"])
    total = df["abundance"].sum()
    if total > 0:
        df["relative"] = df["abundance"] / total * 100

    return _compute_diversity(df)


def parse_fasta(content):
    taxa = []
    abundances = []
    current_taxon = None
    current_seq = []

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith(">"):
            if current_taxon and current_seq:
                taxa.append(current_taxon)
                abundances.append(len("".join(current_seq)))
            current_taxon = line[1:].split()[0]
            current_seq = []
        else:
            current_seq.append(line)

    if current_taxon and current_seq:
        taxa.append(current_taxon)
        abundances.append(len("".join(current_seq)))

    if not taxa:
        return {"error": "Žádné sekvence nenalezeny v FASTA"}

    df = pd.DataFrame({"taxon": taxa, "abundance": abundances})
    total = df["abundance"].sum()
    if total > 0:
        df["relative"] = df["abundance"] / total * 100

    return _compute_diversity(df)


def generate_sample_data():
    data = {
        "taxon": [
            "Bacteroides vulgatus", "Faecalibacterium prausnitzii",
            "Prevotella copri", "Bifidobacterium longum",
            "Lactobacillus plantarum", "Akkermansia muciniphila",
            "Roseburia intestinalis", "Eubacterium rectale",
            "Ruminococcus bromii", "Escherichia coli",
        ],
        "abundance": [
            8500, 6200, 3200, 2800, 1500, 1200, 980, 750, 520, 300,
        ],
    }
    return _compute_diversity(pd.DataFrame(data))


def _compute_diversity(df):
    df["genus"] = df["taxon"].apply(lambda x: x.split()[0] if pd.notna(x) else "Unknown")
    df["phylum"] = df["genus"].map(KNOWN_GENERA).fillna("Other")

    phyla_dist = df.groupby("phylum")["abundance"].sum().reset_index()
    phyla_dist.columns = ["phylum", "abundance"]
    total = phyla_dist["abundance"].sum()
    if total > 0:
        phyla_dist["relative"] = round(phyla_dist["abundance"] / total * 100, 2)
    phyla_dist = phyla_dist.sort_values("relative", ascending=False)
    phyla_dist["color"] = phyla_dist["phylum"].map(PHYLA_COLORS).fillna("#6B7280")

    abundances = df["abundance"].values
    total_reads = int(abundances.sum())
    n_species = len(df)
    rel_abund = abundances / abundances.sum()
    shannon = -np.sum(rel_abund * np.log(rel_abund + 1e-10))
    simpson = 1 - np.sum(rel_abund ** 2)
    if n_species > 1:
        pielou = shannon / np.log(n_species)
    else:
        pielou = 1.0

    f_ratio = None
    firmicutes_row = phyla_dist[phyla_dist["phylum"] == "Firmicutes"]
    bacteroides_row = phyla_dist[phyla_dist["phylum"] == "Bacteroidetes"]
    if not firmicutes_row.empty and not bacteroides_row.empty:
        f_ratio = round(
            firmicutes_row.iloc[0]["abundance"] / bacteroides_row.iloc[0]["abundance"], 2
        )

    return {
        "total_reads": total_reads,
        "n_species": n_species,
        "shannon": round(shannon, 3),
        "simpson": round(simpson, 3),
        "pielou": round(pielou, 3),
        "firmicutes_bacteroidetes_ratio": f_ratio,
        "phylum_distribution": phyla_dist.to_dict("records"),
        "species": df.to_dict("records"),
    }
