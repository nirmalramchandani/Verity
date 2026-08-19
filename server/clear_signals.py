import asyncio
from db.mongo import high_conviction_signals_collection, portfolio_holdings_collection

async def clear_signals():
    print("Clearing signals...")
    res_signals = high_conviction_signals_collection.delete_many({})
    print(f"{res_signals.deleted_count} signals deleted.")
    
    print("Clearing holdings...")
    res_holdings = portfolio_holdings_collection.delete_many({})
    print(f"{res_holdings.deleted_count} holdings deleted.")

if __name__ == "__main__":
    asyncio.run(clear_signals())
