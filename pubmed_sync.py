import os
import sys
import time
import json
import logging
from datetime import datetime
from xml.etree import ElementTree

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules.config import (
    PUBMED_API_KEY, PUBMED_EMAIL, SEARCH_QUERIES, DATA_DIR
)
from modules.database import Database
from modules.study_filters import filter_evidence_level, extract_latin_names, is_outdated

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pubmed_sync")

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def search_pubmed(query, max_results=50, retstart=0):
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retstart": retstart,
        "retmode": "json",
        "sort": "date",
    }
    if PUBMED_API_KEY:
        params["api_key"] = PUBMED_API_KEY
    if PUBMED_EMAIL:
        params["email"] = PUBMED_EMAIL

    try:
        resp = requests.get(PUBMED_SEARCH, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        ids = data.get("esearchresult", {}).get("idlist", [])
        total = int(data.get("esearchresult", {}).get("count", 0))
        log.info(f"Query '{query}': found {total} results, fetched {len(ids)} IDs")
        return ids
    except Exception as e:
        log.error(f"Search failed for '{query}': {e}")
        return []


def fetch_details(pubmed_ids):
    if not pubmed_ids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pubmed_ids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    if PUBMED_API_KEY:
        params["api_key"] = PUBMED_API_KEY
    if PUBMED_EMAIL:
        params["email"] = PUBMED_EMAIL

    try:
        resp = requests.get(PUBMED_FETCH, params=params, timeout=60)
        resp.raise_for_status()
        return _parse_articles(resp.text)
    except Exception as e:
        log.error(f"Fetch failed: {e}")
        return []


def _parse_articles(xml_text):
    articles = []
    root = ElementTree.fromstring(xml_text)

    for article_elem in root.findall(".//PubmedArticle"):
        try:
            medline = article_elem.find(".//MedlineCitation")
            if medline is None:
                continue

            article = medline.find("Article")
            if article is None:
                continue

            pmid = medline.findtext("PMID", "")
            title = article.findtext("ArticleTitle", "")
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(
                (part.text or "") for part in abstract_parts
            ) if abstract_parts else ""
            if not abstract:
                continue

            authors = []
            author_list = article.find(".//AuthorList")
            if author_list is not None:
                for author in author_list.findall("Author"):
                    last = author.findtext("LastName", "")
                    fore = author.findtext("ForeName", "")
                    if last and fore:
                        authors.append(f"{last} {fore}")
            authors_str = "; ".join(authors[:10])

            journal = article.findtext(".//Journal/Title", "")
            pub_date = _parse_date(article.find(".//Journal/JournalIssue/PubDate"))

            article_id = article_elem.find(".//ArticleIdList")
            doi = ""
            if article_id is not None:
                for aid in article_id.findall("ArticleId"):
                    if aid.get("IdType") == "doi":
                        doi = aid.text or ""
                        break
            url = f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            evidence = filter_evidence_level(abstract)
            latin_names = extract_latin_names(abstract)
            outdated = is_outdated(pub_date)

            articles.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors_str,
                "journal": journal,
                "pub_date": pub_date,
                "url": url,
                "doi": doi,
                "evidence_level": evidence,
                "latin_names": latin_names,
                "outdated": outdated,
            })
        except Exception as e:
            log.warning(f"Parse error for article: {e}")
            continue

    return articles


def _parse_date(pub_date_elem):
    if pub_date_elem is None:
        return ""
    year = pub_date_elem.findtext("Year", "")
    month = pub_date_elem.findtext("Month", "01")
    day = pub_date_elem.findtext("Day", "01")
    if not year:
        medline_date = pub_date_elem.findtext("MedlineDate", "")
        if medline_date:
            year = medline_date[:4]
    if year:
        try:
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except Exception:
            return year
    return ""


def sync_all(db: Database):
    all_ids = set()
    for query in SEARCH_QUERIES:
        ids = search_pubmed(query, max_results=30)
        all_ids.update(ids)
        time.sleep(0.4)

    log.info(f"Total unique PMIDs to fetch: {len(all_ids)}")
    id_list = list(all_ids)
    added = 0

    for i in range(0, len(id_list), 50):
        batch = id_list[i:i + 50]
        articles = fetch_details(batch)
        for art in articles:
            study_id = f"pubmed_{art['pmid']}"
            if db.add_study(
                study_id=study_id,
                title=art["title"],
                abstract=art["abstract"],
                authors=art["authors"],
                journal=art["journal"],
                pub_date=art["pub_date"],
                url=art["url"],
                evidence_level=art["evidence_level"],
            ):
                added += 1

        if i % 100 == 0 and i > 0:
            log.info(f"Progress: {i}/{len(id_list)}")

    db.mark_synced()
    log.info(f"Sync complete. Added {added} new studies. Total: {db.get_stats()['total_studies']}")
    return added


def sync_if_needed(db: Database, force=False):
    if force or db.check_sync_needed(hours=24):
        log.info("Starting scheduled PubMed sync...")
        return sync_all(db)
    log.info("Sync not needed (last sync < 24h ago)")
    return 0


if __name__ == "__main__":
    db = Database()
    count = sync_all(db)
    print(json.dumps({"added": count, "total": db.get_stats()["total_studies"]}))
