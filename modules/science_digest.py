from datetime import datetime, timedelta
from modules.database import Database
from modules.config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL


def generate_digest(db: Database, ai_client=None) -> dict:
    studies = db.get_latest_studies(n=30)
    if not studies:
        return {"digest": "Žádné nové studie k dispozici.", "count": 0}

    recent = [s for s in studies if s.get("pub_date", "") >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")]
    recent = recent[:15]

    if not recent:
        recent = studies[:15]

    if ai_client and DEEPSEEK_API_KEY:
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
        "Jsi vědecký asistent specializující se na mikrobiom, fermentaci a rostlinnou výživu.",
        "Vytvoř stručný ranní souhrn (5-7 odrážek) z následujících vědeckých studií:",
        "Zaměř se na praktické implikace pro veganskou stravu a fermentaci.",
        "Používej laický srozumitelný jazyk. Každou odrážku začni klíčovým zjištěním.",
        "Studie:",
    ]
    for s in studies[:10]:
        title = s.get("title", "Neznámý titul")
        level = s.get("evidence_level", "Unknown")
        date = s.get("pub_date", "")[:10]
        prompt_lines.append(f"- [{level}] ({date}) {title}")

    prompt_lines.append("\nSouhrn:")
    prompt = "\n".join(prompt_lines)

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Chyba při generování AI souhrnu: {e}"


def _rule_summarize(studies):
    lines = ["📰 **Ranní vědecký digest** (automatický)", ""]
    evidence_order = {"Meta-analysis": 0, "RCT": 1, "Cohort": 2, "Case-Control": 3, "In-vitro": 4, "Animal": 5, "Unknown": 6}

    sorted_studies = sorted(
        studies[:10],
        key=lambda s: (evidence_order.get(s.get("evidence_level", "Unknown"), 99), s.get("pub_date", "")),
    )

    for s in sorted_studies:
        icon = "📊" if s.get("evidence_level") in ["Meta-analysis", "RCT"] else "📋"
        outdated = " ⚠️ Zastaralé" if s.get("pub_date") and s["pub_date"] < (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d") else ""
        lines.append(f"{icon} **{s.get('title', 'Bez názvu')}**{outdated}")
        lines.append(f"   └ {s.get('authors', '')[:80]} | {s.get('journal', '')} | {s.get('pub_date', '')[:10]}")
        lines.append(f"   └ Evidence: {s.get('evidence_level', 'N/A')}")

    return "\n".join(lines)
