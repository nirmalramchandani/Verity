from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)

db = client["smart_money"]

investors_collection = db["investors"]
investor_metrics_collection = db["investor_metrics"]
ingestion_metadata_collection = db["ingestion_metadata"]
high_conviction_signals_collection = db["high_conviction_signals"]
portfolio_holdings_collection = db["portfolio_holdings"]
