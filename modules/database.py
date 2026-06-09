import json
import sqlite3
import os
from datetime import datetime
import chromadb
from chromadb.config import Settings
from modules.config import CHROMA_PATH, DB_PATH, SYNC_FILE


class Database:
    def __init__(self):
        os.makedirs(CHROMA_PATH, exist_ok=True)
        self.chroma = chromadb.PersistentClient(
            path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.chroma.get_or_create_collection(
            name="pubmed_studies", metadata={"hnsw:space": "cosine"}
        )
        self._init_sqlite()

    def _init_sqlite(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stool_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, bristol INTEGER, symptoms TEXT,
                food TEXT, probiotics TEXT, notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fermentation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, sugar REAL, temperature REAL,
                ph REAL, strains TEXT, duration REAL, notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, product_name TEXT, ingredients TEXT,
                flagged_additives TEXT, safe BOOLEAN
            )
        """)
        conn.commit()
        conn.close()

    def add_study(self, study_id, title, abstract, authors, journal, pub_date, url, evidence_level):
        existing = self.collection.get(ids=[study_id])
        if existing and existing["ids"]:
            return False
        self.collection.add(
            ids=[study_id],
            documents=[f"{title}\n\n{abstract}"],
            metadatas=[{
                "title": title,
                "authors": authors,
                "journal": journal,
                "pub_date": pub_date,
                "url": url,
                "evidence_level": evidence_level,
                "added": datetime.now().isoformat()
            }]
        )
        return True

    def search_studies(self, query, n_results=5, evidence_filter=None):
        results = self.collection.query(query_texts=[query], n_results=50)
        if not results["ids"]:
            return []
        items = []
        for i, sid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            if evidence_filter and meta.get("evidence_level") not in evidence_filter:
                continue
            items.append({
                "id": sid,
                "title": meta.get("title", ""),
                "authors": meta.get("authors", ""),
                "journal": meta.get("journal", ""),
                "pub_date": meta.get("pub_date", ""),
                "url": meta.get("url", ""),
                "evidence_level": meta.get("evidence_level", "Unknown"),
                "distance": results["distances"][0][i] if results.get("distances") else 0
            })
            if len(items) >= n_results:
                break
        return items

    def get_latest_studies(self, n=20):
        results = self.collection.get()
        if not results["ids"]:
            return []
        items = []
        for i in range(len(results["ids"])):
            items.append({
                "id": results["ids"][i],
                **results["metadatas"][i]
            })
        items.sort(key=lambda x: x.get("pub_date", ""), reverse=True)
        return items[:n]

    def get_stats(self):
        count = self.collection.count()
        results = self.collection.get()
        evidence_counts = {}
        if results["metadatas"]:
            for m in results["metadatas"]:
                el = m.get("evidence_level", "Unknown")
                evidence_counts[el] = evidence_counts.get(el, 0) + 1
        return {"total_studies": count, "evidence_counts": evidence_counts}

    def add_stool_log(self, date, bristol, symptoms, food, probiotics, notes):
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO stool_logs (date, bristol, symptoms, food, probiotics, notes) VALUES (?,?,?,?,?,?)",
            (date, bristol, symptoms, food, probiotics, notes)
        )
        conn.commit()
        conn.close()

    def get_stool_logs(self, limit=100):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT * FROM stool_logs ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return rows

    def add_fermentation_log(self, date, sugar, temperature, ph, strains, duration, notes):
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO fermentation_logs (date, sugar, temperature, ph, strains, duration, notes) VALUES (?,?,?,?,?,?,?)",
            (date, sugar, temperature, ph, strains, duration, notes)
        )
        conn.commit()
        conn.close()

    def get_fermentation_logs(self, limit=50):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT * FROM fermentation_logs ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return rows

    def add_scan_log(self, date, product_name, ingredients, flagged_additives, safe):
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO scan_logs (date, product_name, ingredients, flagged_additives, safe) VALUES (?,?,?,?,?)",
            (date, product_name, ingredients, json.dumps(flagged_additives), safe)
        )
        conn.commit()
        conn.close()

    def get_recent_scans(self, limit=20):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT * FROM scan_logs ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return rows

    def check_sync_needed(self, hours=24):
        if not os.path.exists(SYNC_FILE):
            return True
        with open(SYNC_FILE) as f:
            data = json.load(f)
        last = datetime.fromisoformat(data["last_sync"])
        return (datetime.now() - last).total_seconds() > hours * 3600

    def mark_synced(self):
        os.makedirs(os.path.dirname(SYNC_FILE), exist_ok=True)
        with open(SYNC_FILE, "w") as f:
            json.dump({"last_sync": datetime.now().isoformat()}, f)
