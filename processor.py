import pandas as pd
import os
import logging

# ── Logging ──────────────────────────────────────────────────────────────────
os.makedirs('pca_data/logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pca_data/logs/processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── File Paths ────────────────────────────────────────────────────────────────
INPUT_PATH  = 'pca_data/combined_pca_data.csv'   # output of scraper.py
OUTPUT_PATH = 'pca_data/staged_pca_data.csv'     # input to loader.py

# ── Antidepressant Reference List ─────────────────────────────────────────────
# Only rows matching these BNF chemical substance names will be retained.
ANTIDEPRESSANTS = [
    'Agomelatine', 'Amitriptyline hydrochloride', 'Amoxapine',
    'Citalopram hydrobromide', 'Citalopram hydrochloride',
    'Clomipramine hydrochloride', 'Dosulepin hydrochloride', 'Doxepin',
    'Duloxetine hydrochloride', 'Escitalopram', 'Fluoxetine hydrochloride',
    'Flupentixol hydrochloride', 'Fluvoxamine maleate',
    'Imipramine hydrochloride', 'Isocarboxazid', 'Lofepramine hydrochloride',
    'Mianserin hydrochloride', 'Mirtazapine', 'Moclobemide',
    'Nefazodone hydrochloride', 'Nortriptyline', 'Oxitriptan',
    'Paroxetine hydrochloride', 'Phenelzine sulfate', 'Reboxetine',
    'Sertraline hydrochloride', 'Tranylcypromine sulfate',
    'Trazodone hydrochloride', 'Trimipramine maleate', 'Tryptophan',
    'Venlafaxine', 'Vortioxetine',
]


def main():

    # ── Step 1: Load ──────────────────────────────────────────────────────────
    logger.info("Loading combined data...")
    df = pd.read_csv(INPUT_PATH)
    logger.info(f"Loaded {len(df):,} rows.")

    # ── Step 2: Drop rows with missing values ─────────────────────────────────
    # Any row missing a region, drug name, item count, or cost is unusable.
    before = len(df)
    df = df.dropna(subset=['YEAR_MONTH', 'REGION_NAME', 'BNF_CHEMICAL_SUBSTANCE', 'ITEMS', 'NIC'])
    logger.info(f"Dropped {before - len(df):,} rows with missing values.")

    # ── Step 3: Strip whitespace from text columns ────────────────────────────
    # Trailing spaces cause drugs like 'Sertraline hydrochloride ' to be
    # treated as a different drug — a silent but serious data quality issue.
    df['REGION_NAME']            = df['REGION_NAME'].str.strip()
    df['BNF_CHEMICAL_SUBSTANCE'] = df['BNF_CHEMICAL_SUBSTANCE'].str.strip()

    # ── Step 4: Filter to antidepressants only ────────────────────────────────
    before = len(df)
    df = df[df['BNF_CHEMICAL_SUBSTANCE'].isin(ANTIDEPRESSANTS)].copy()
    logger.info(f"Filtered to antidepressants: {len(df):,} rows retained, {before - len(df):,} removed.")
    logger.info(f"Unique antidepressants found: {df['BNF_CHEMICAL_SUBSTANCE'].nunique()}")

    # ── Step 5: Standardise region names to Title Case ────────────────────────
    # Converts 'NORTH WEST' → 'North West' for clean display in Power BI.
    df['REGION_NAME'] = df['REGION_NAME'].str.title()

    # ── Step 6: Aggregate to region level ────────────────────────────────────
    # The raw NHS BSA data is published at GP practice or ICB sub-level,
    # meaning there are many rows per drug-region-month combination.
    # We sum ITEMS and NIC up to the region level — exactly as your
    # notebook does in cell 13 with groupby().agg().
    before = len(df)
    df = df.groupby(
        ['YEAR_MONTH', 'REGION_NAME', 'BNF_CHEMICAL_SUBSTANCE'],
        as_index=False
    ).agg(
        ITEMS=('ITEMS', 'sum'),
        NIC=('NIC',   'sum')
    )
    logger.info(f"Aggregated from {before:,} rows to {len(df):,} rows at region level.")

    # ── Step 7: Derive YEAR column from YEAR_MONTH ────────────────────────────
    # Must happen before Step 8 which changes the YEAR_MONTH format.
    df.insert(0, 'YEAR', df['YEAR_MONTH'].astype(str).str[:4].astype(int))

    # ── Step 8: Convert YEAR_MONTH from 202101 format to 2021-01 format ───────
    # ISO 8601 format sorts correctly alphabetically and loads cleanly into MySQL.
    df['YEAR_MONTH'] = pd.to_datetime(
        df['YEAR_MONTH'].astype(str), format='%Y%m'
    ).dt.strftime('%Y-%m')

    # ── Step 9: Enforce correct data types ────────────────────────────────────
    # Prevents type mismatch errors when loader.py inserts into MySQL.
    df['YEAR']  = df['YEAR'].astype(int)
    df['ITEMS'] = df['ITEMS'].astype(int)
    df['NIC']   = df['NIC'].astype(float).round(2)

    # ── Step 10: Select and order final columns ───────────────────────────────
    df = df[['YEAR', 'YEAR_MONTH', 'REGION_NAME', 'BNF_CHEMICAL_SUBSTANCE', 'ITEMS', 'NIC']]

    # ── Step 11: Save staged output ───────────────────────────────────────────
    df.to_csv(OUTPUT_PATH, index=False)

    logger.info(f"Staged data saved: {len(df):,} rows → {OUTPUT_PATH}")
    logger.info("Next step: run loader.py to load into MySQL.")
    print(f"\nDone. {len(df):,} rows saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
