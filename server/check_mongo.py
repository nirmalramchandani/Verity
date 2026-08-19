from db.mongo import investors_collection
doc = investors_collection.find_one({"portfolio_state": {"$exists": True}})
if doc:
    keys = list(doc["portfolio_state"].keys())
    if keys:
        print(f"First symbol: {keys[0]}")
        print(f"Details: {doc['portfolio_state'][keys[0]]}")
    else:
        print("portfolio_state is empty")
