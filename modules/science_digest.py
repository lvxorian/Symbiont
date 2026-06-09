from datetime import datetime, timedelta
from modules.database import Database
from modules.config import GEMINI_API_KEY, GEMINI_MODEL
import streamlit as st
import pandas as pd
import plotly.express as px


def generate_digest(db: Database, ai_client=None) -> dict:
    studies = db.get_latest_studies(n=30)
    if not studies:
        return {"digest": "Zadne nove studie k dispozici.", "count": 0}

    recent = [s for s in studies if s.get("pub_date", "") >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")]
    recent = recent[:15]

    if not recent:
        recent = studies[:15]

    if ai_client and GEMINI_API_KEY:
        digest_text = _llm_summarize(ai_client, recent)
    else:
        digest_text = _rule_summarize(recent)

    evidence_breakdown = {}
    for s in recent:
        level = s.get("evidence_level", "Unknown")
        evidence_breakdown[level] = evidence_breakdown.get(level, 0) + 1

    return {
        "digest": digest_text,
        "count": len(recent),
        "studies": recent,
        "evidence_breakdown": evidence_breakdown,
        "generated": datetime.now().isoformat(),
    }


def _llm_summarize(client, studies):
    prompt_lines = [
        "Jsi vedecky asistent specializujici se na mikrobiom, fermentaci a rostlinnou vyzivu.",
        "Vytvor strucny ranni souhrn (5-7 odrazek) z nasledujicich vedeckych studii:",
        "Zamer se na prakticke implikace pro veganskou stravu a fermentaci.",
        "Pouzivej laicky srozumitelny jazyk. Kazdou odrazku zacni klicovym zjistenim.",
        "Studie:",
    ]
    for s in studies[:10]:
        title = s.get("title", "Neznamy titul")
        level = s.get("evidence_level", "Unknown")
        date = s.get("pub_date", "")[:10]
        prompt_lines.append(f"- [{level}] ({date}) {title}")

    prompt_lines.append("\nSouhrn:")
    prompt = "\n".join(prompt_lines)

    try:
        response = client.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Chyba pri generovani AI souhrnu: {e}"


def _rule_summarize(studies):
    lines = ["Ranni vedecky digest (automaticky)", ""]
    evidence_order = {"Meta-analysis": 0, "RCT": 1, "Cohort": 2, "Case-Control": 3, "In-vitro": 4, "Animal": 5, "Unknown": 6}

    sorted_studies = sorted(
        studies[:10],
        key=lambda s: (evidence_order.get(s.get("evidence_level", "Unknown"), 99), s.get("pub_date", "")),
    )

    for s in sorted_studies:
        icon = "📊" if s.get("evidence_level") in ["Meta-analysis", "RCT"] else "📋"
        outdated = " Zastarale" if s.get("pub_date") and s["pub_date"] < (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d") else ""
        lines.append(f"{icon} **{s.get('title', 'Bez nazvu')}**{outdated}")
        lines.append(f"   └ {s.get('authors', '')[:80]} | {s.get('journal', '')} | {s.get('pub_date', '')[:10]}")
        lines.append(f"   └ Evidence: {s.get('evidence_level', 'N/A')}")

    return "\n".join(lines)


def render_digest(db):
    from pubmed_sync import sync_if_needed

    st.markdown("### Morning Science Digest")
    st.caption("Ranni souhrn nejnovejsich studii")
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Studii", db.get_stats()["total_studies"])
        if st.button("Generovat digest", use_container_width=True):
            with st.spinner("Generuji..."):
                st.session_state.current_digest = generate_digest(db, ai_client=st.session_state.get("gemini_model"))
        if st.button("Sync PubMed", use_container_width=True):
            with st.spinner("Stahuji studie..."):
                a = sync_if_needed(db, force=True)
                st.success(f"Pridano {a} studii") if a else st.info("Zadne nove")
    with col2:
        if "current_digest" in st.session_state:
            d = st.session_state.current_digest
            st.markdown(f"<div class='sci-fi-card'>{d['digest']}</div>", unsafe_allow_html=True)
            if d.get("evidence_breakdown"):
                df = pd.DataFrame(list(d["evidence_breakdown"].items()), columns=["Level","Count"])
                fig = px.pie(df, values="Count", names="Level", color_discrete_sequence=["#22C55E","#00F2FE","#F59E0B","#EF4444"])
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", height=250)
                st.plotly_chart(fig, use_container_width=True)
            with st.expander("Studie"):
                for s in d["studies"]:
                    badge = "📊" if s.get("evidence_level") in ("RCT","Meta-analysis") else "📋"
                    st.markdown(f"{badge} **{s.get('title','')}**")
                    st.caption(f"{s.get('authors','')[:60]} | {s.get('journal','')} | {s.get('pub_date','')[:10]}")
        else:
            st.info("Klikni na Generovat digest")
