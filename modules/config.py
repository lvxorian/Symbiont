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
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

DEEPSEEK_MODEL = "deepseek-chat"
WHISPER_MODEL = "whisper-1"

SEARCH_QUERIES = [
    "gut microbiome vegan dietary fiber",
    "short chain fatty acids SCFA plant-based",
    "fermented foods microbiome Lactobacillus",
    "Bifidobacterium prebiotics vegan",
    "probiotics gut-brain axis plant protein",
    "Phytate deactivation legumes fermentation",
    "Lactobacillus plantarum fermentation",
]
