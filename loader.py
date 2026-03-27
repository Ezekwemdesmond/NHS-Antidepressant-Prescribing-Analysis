import pandas as pd
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os
import logging

# Logging 
os.makedirs('pca_data/logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pca_data/logs/loader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reads database credentials from the .env file.
load_dotenv()

DB_CONFIG = {
    'host'    : os.getenv('DB_HOST'),
    'port'    : int(os.getenv('DB_PORT', 3306)),
    'user'    : os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

# File Paths
STAGED_INPUT_PATH   = 'pca_data/staged_pca_data.csv'  # output of processor.py
FORECAST_INPUT_PATH = 'pca_data/forecast.csv'         # output of forecast.py


# CONNECTION
def get_connection():
    """Connect to MySQL using credentials from the .env file."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        logger.info("Connected to MySQL successfully.")
        return conn
    except Error as e:
        logger.error(f"Failed to connect to MySQL: {e}")
        logger.error(
            "Check that:\n"
            "  1. MySQL is running\n"
            "  2. Your .env file has the correct credentials\n"
            "  3. The nhs_prescribing database exists (run 01_schema.sql first)"
        )
        raise


# LOAD DIMENSION TABLES
def load_dates(conn, df):
    """
    Insert one row per unique year-month into dates.
    Derives month number and month name from the YEAR_MONTH column.
    Note: `year` and `month` are reserved words — backticks used in SQL.
    """
    cursor = conn.cursor()

    unique_dates = df[['YEAR', 'YEAR_MONTH']].drop_duplicates()
    inserted = 0

    for _, row in unique_dates.iterrows():
        year_month = row['YEAR_MONTH']
        year       = int(row['YEAR'])
        month      = int(year_month.split('-')[1])
        month_name = pd.to_datetime(year_month + '-01').strftime('%B')

        cursor.execute("""
            INSERT IGNORE INTO dates (`year_month`, `year`, `month`, month_name)
            VALUES (%s, %s, %s, %s)
        """, (year_month, year, month, month_name))
        inserted += cursor.rowcount

    conn.commit()
    cursor.close()
    logger.info(f"dates: {inserted} new rows inserted.")


def load_regions(conn, df):
    """Insert one row per unique NHS region into regions."""
    cursor = conn.cursor()

    inserted = 0
    for region_name in df['REGION_NAME'].unique():
        cursor.execute("""
            INSERT IGNORE INTO regions (region_name)
            VALUES (%s)
        """, (region_name,))
        inserted += cursor.rowcount

    conn.commit()
    cursor.close()
    logger.info(f"regions: {inserted} new rows inserted.")


def load_drugs(conn, df):
    """Insert one row per unique antidepressant substance into drugs."""
    cursor = conn.cursor()

    inserted = 0
    for drug_name in df['BNF_CHEMICAL_SUBSTANCE'].unique():
        cursor.execute("""
            INSERT IGNORE INTO drugs (bnf_chemical_substance)
            VALUES (%s)
        """, (drug_name,))
        inserted += cursor.rowcount

    conn.commit()
    cursor.close()
    logger.info(f"drugs: {inserted} new rows inserted.")


# LOAD FACT TABLE
def load_prescriptions(conn, df):
    """
    Load all prescription records into prescriptions.
    Looks up foreign key IDs from memory then batch inserts into the table.
    """
    cursor = conn.cursor()

    # Build ID lookup dictionaries from dimension tables
    cursor.execute("SELECT date_id, `year_month` FROM dates")
    date_lookup = {row[1]: row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT region_id, region_name FROM regions")
    region_lookup = {row[1]: row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT drug_id, bnf_chemical_substance FROM drugs")
    drug_lookup = {row[1]: row[0] for row in cursor.fetchall()}

    # Build rows to insert
    rows_to_insert = []
    skipped = 0

    for _, row in df.iterrows():
        date_id   = date_lookup.get(row['YEAR_MONTH'])
        region_id = region_lookup.get(row['REGION_NAME'])
        drug_id   = drug_lookup.get(row['BNF_CHEMICAL_SUBSTANCE'])

        if not all([date_id, region_id, drug_id]):
            skipped += 1
            continue

        rows_to_insert.append((
            date_id,
            region_id,
            drug_id,
            int(row['ITEMS']),
            float(row['NIC'])
        ))

    if skipped > 0:
        logger.warning(f"Skipped {skipped:,} rows — could not resolve lookup IDs.")

    # Batch insert in groups of 1,000
    batch_size = 1000
    inserted   = 0
    total      = len(rows_to_insert)

    for i in range(0, total, batch_size):
        batch = rows_to_insert[i : i + batch_size]
        cursor.executemany("""
            INSERT IGNORE INTO prescriptions
                (date_id, region_id, drug_id, items, nic)
            VALUES
                (%s, %s, %s, %s, %s)
        """, batch)
        inserted += cursor.rowcount
        conn.commit()
        logger.info(
            f"  Progress: {min(i + batch_size, total):,} / {total:,} rows processed."
        )

    cursor.close()
    logger.info(f"prescriptions: {inserted:,} new rows inserted.")


# LOAD FORECAST TABLE
def load_forecast(conn, df):
    """
    Load the Prophet forecast output into the forecast table.
    Reads from pca_data/forecast.csv — output of forecast.py.

    Uses INSERT IGNORE for idempotency — re-running will not duplicate rows
    because year_month has a UNIQUE constraint in 04_forecast_schema.sql.

    Batch inserts in groups of 1,000 — consistent with load_prescriptions().
    """
    cursor = conn.cursor()

    # Build rows to insert
    # actual_items, actual_nic, actual_cpi are NULL for future forecast months
    rows_to_insert = []

    for _, row in df.iterrows():
        rows_to_insert.append((
            str(row['year_month']),

            # Actual values — NULL for future forecast months
            int(row['actual_items'])   if pd.notna(row.get('actual_items'))   else None,
            float(row['actual_nic'])   if pd.notna(row.get('actual_nic'))     else None,
            float(row['actual_cpi'])   if pd.notna(row.get('actual_cpi'))     else None,

            # Items forecast with confidence interval
            float(row['items_forecast']),
            float(row['items_lower']),
            float(row['items_upper']),

            # NIC forecast with confidence interval
            float(row['nic_forecast']),
            float(row['nic_lower']),
            float(row['nic_upper']),

            # Cost per item forecast with confidence interval
            float(row['cpi_forecast']),
            float(row['cpi_lower']),
            float(row['cpi_upper']),

            # is_forecast flag — 1 for forecast months, 0 for historical
            int(row['is_forecast'])
        ))

    # Batch insert in groups of 1,000
    batch_size = 1000
    inserted   = 0
    total      = len(rows_to_insert)

    for i in range(0, total, batch_size):
        batch = rows_to_insert[i : i + batch_size]
        cursor.executemany("""
            INSERT IGNORE INTO forecast (
                `year_month`,
                actual_items, actual_nic, actual_cpi,
                items_forecast, items_lower, items_upper,
                nic_forecast,   nic_lower,   nic_upper,
                cpi_forecast,   cpi_lower,   cpi_upper,
                is_forecast
            )
            VALUES (
                %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s
            )
        """, batch)
        inserted += cursor.rowcount
        conn.commit()
        logger.info(
            f"  Progress: {min(i + batch_size, total):,} / {total:,} rows processed."
        )

    cursor.close()
    logger.info(f"forecast: {inserted:,} new rows inserted.")


def main():
    logger.info("=" * 60)
    logger.info("NHS PCA DATA LOADER — STARTING")
    logger.info(f"Input   : {STAGED_INPUT_PATH}")
    logger.info(f"Forecast: {FORECAST_INPUT_PATH}")
    logger.info(f"Target  : MySQL -> {DB_CONFIG['database']}")
    logger.info("=" * 60)
    logger.info(
        "NOTE: This script assumes the database and tables already exist.\n"
        "      If not, run sql/01_schema.sql and sql/04_forecast_schema.sql first."
    )

    # ── Load staged CSV ───────────────────────────────────────────────────────
    if not os.path.exists(STAGED_INPUT_PATH):
        raise FileNotFoundError(
            f"Staged file not found: {STAGED_INPUT_PATH}\n"
            f"Run processor.py first to generate this file."
        )

    logger.info("Loading staged data...")
    df = pd.read_csv(STAGED_INPUT_PATH)
    logger.info(f"Loaded {len(df):,} rows from staged CSV.")

    # ── Connect and load ──────────────────────────────────────────────────────
    conn = get_connection()

    try:
        # Load dimension tables first — prescriptions depends on their IDs
        logger.info("Loading dimension tables...")
        load_dates(conn, df)
        load_regions(conn, df)
        load_drugs(conn, df)

        # Load prescriptions fact table
        logger.info("Loading prescriptions...")
        load_prescriptions(conn, df)

        # Load forecast table — only if forecast.csv exists
        # forecast.py must be run before loader.py to generate this file.
        if os.path.exists(FORECAST_INPUT_PATH):
            logger.info("Loading forecast data...")
            forecast_df = pd.read_csv(FORECAST_INPUT_PATH)
            logger.info(f"Loaded {len(forecast_df):,} rows from forecast CSV.")
            load_forecast(conn, forecast_df)
        else:
            logger.warning(
                f"Forecast file not found: {FORECAST_INPUT_PATH}\n"
                f"Skipping forecast load. Run forecast.py to generate this file."
            )

        logger.info("=" * 60)
        logger.info("LOADING COMPLETE")
        logger.info("Next step: open Power BI and refresh all tables.")
        logger.info("=" * 60)

    except Error as e:
        logger.error(f"Database error: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()
        logger.info("MySQL connection closed.")


if __name__ == "__main__":
    main()
