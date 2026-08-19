import pandas as pd
import json
import os


def clean_transactions(file_path: str) -> pd.DataFrame:
    df = pd.read_csv(file_path)

    # 1. Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    # Expected original columns (NSE bulk deal / insider trade format)
    column_mapping = {
        "date": "date",
        "symbol": "stock_symbol",
        "security name": "security_name",
        "client name": "investor_name",
        "buy / sell": "transaction_type",
        "quantity traded": "quantity",
        "trade price / wght. avg. price": "price",
    }

    df = df.rename(columns=column_mapping)

    # 2. Keep only required columns
    required_columns = [
        "date",
        "stock_symbol",
        "investor_name",
        "transaction_type",
        "quantity",
        "price",
    ]

    df = df[required_columns]

    # 3. Clean quantity (remove Indian comma formatting e.g. 1,00,000)
    df["quantity"] = (
        df["quantity"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .astype("int64")
    )

    # 4. Clean price (remove Indian comma formatting)
    df["price"] = (
        df["price"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .astype(float)
    )

    # 5. Normalize transaction type to BUY / SELL
    df["transaction_type"] = df["transaction_type"].str.strip().str.upper()

    # 6. Standardize date format to YYYY-MM-DD
    df["date"] = pd.to_datetime(
        df["date"], format="mixed", dayfirst=True, errors="coerce"
    ).dt.date

    # 7. Apply Aliases and Symbol Mapping
    base_dir = os.path.dirname(__file__)
    try:
        with open(os.path.join(base_dir, "investor_aliases.json"), "r") as f:
            aliases = json.load(f)
        df["investor_name"] = df["investor_name"].replace(aliases)
    except FileNotFoundError:
        pass
        
    try:
        with open(os.path.join(base_dir, "symbol_mapping.json"), "r") as f:
            symbol_map = json.load(f)
        df["stock_symbol"] = df["stock_symbol"].replace(symbol_map)
    except FileNotFoundError:
        pass

    # 8. Deduplication
    df = df.drop_duplicates()

    # 9. Drop rows with any missing values
    df = df.dropna()

    # 10. Remove Intraday Orders (Same day, Same investor, Same stock, Buy Qty == Sell Qty)
    # We group by date, investor, symbol, and quantity, and if both a BUY and a SELL exist, we drop them.
    intraday_mask = df.groupby(["date", "investor_name", "stock_symbol", "quantity"])["transaction_type"].transform('nunique') == 2
    df = df[~intraday_mask].reset_index(drop=True)

    return df


def clean_events(file_path: str) -> pd.DataFrame:
    df = pd.read_csv(file_path)

    # 1. Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    # Expected original columns (NSE corporate actions format)
    column_mapping = {
        "symbol": "stock_symbol",
        "company name": "company_name",
        "series": "series",
        "purpose": "purpose",
        "face value": "face_value",
        "ex-date": "ex_date",
        "record date": "record_date",
        "book closure start date": "book_closure_start",
        "book closure end date": "book_closure_end",
    }

    df = df.rename(columns=column_mapping)

    # 2. Keep only relevant columns
    required_columns = [
        "stock_symbol",
        "company_name",
        "series",
        "purpose",
        "ex_date",
        "record_date",
    ]

    df = df[required_columns]

    # 3. Strip whitespace from string columns
    for col in ["stock_symbol", "company_name", "series", "purpose"]:
        df[col] = df[col].astype(str).str.strip()

    # 4. Standardize date formats to YYYY-MM-DD
    df["ex_date"] = pd.to_datetime(
        df["ex_date"], dayfirst=True, errors="coerce"
    ).dt.date
    df["record_date"] = pd.to_datetime(
        df["record_date"], dayfirst=True, errors="coerce"
    ).dt.date

    # 5. Drop rows with missing critical fields
    df = df.dropna(subset=["stock_symbol", "ex_date"])

    return df
