import pandas as pd
import numpy as np
import re
from io import StringIO
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px


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


def render_dna():
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
