import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_PATH = os.path.join(DATA_DIR, "chromadb")
DB_PATH = os.path.join(DATA_DIR, "symbiont.db")
SYNC_FILE = os.path.join(DATA_DIR, "last_sync.json")

PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
PUBMED_EMAIL = os.getenv("PUBMED_EMAIL", "user@example.com")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_FALLBACK_MODELS = ["gemini-1.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash-exp"]

SEARCH_QUERIES = [
    "gut microbiome vegan dietary fiber",
    "short chain fatty acids SCFA plant-based",
    "fermented foods microbiome Lactobacillus",
    "Bifidobacterium prebiotics vegan",
    "probiotics gut-brain axis plant protein",
    "Phytate deactivation legumes fermentation",
    "Lactobacillus plantarum fermentation",
]
