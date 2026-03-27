import pandas as pd
import numpy as np
import os
import logging

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs('pca_data/logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pca_data/logs/forecast.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── File Paths ────────────────────────────────────────────────────────────────
INPUT_PATH  = 'pca_data/staged_pca_data.csv'  # output of processor.py
OUTPUT_PATH = 'pca_data/forecast.csv'         # input to loader.py

# ── Forecast Configuration ────────────────────────────────────────────────────
FORECAST_PERIODS   = 12      # number of months to forecast ahead
CONFIDENCE_INTERVAL = 0.80   # 80% confidence interval — matches Power BI template


def build_monthly_totals(df):
    """
    Aggregate staged data to monthly national totals.
    The staged data is at drug-region-month level — we sum across all drugs
    and regions to get the national monthly total for items and cost (NIC).
    """
    monthly = df.groupby('YEAR_MONTH', as_index=False).agg(
        total_items=('ITEMS', 'sum'),
        total_nic  =('NIC',   'sum')
    )

    # Convert YEAR_MONTH string (2021-01) to datetime for Prophet
    monthly['ds'] = pd.to_datetime(monthly['YEAR_MONTH'])
    monthly = monthly.sort_values('ds').reset_index(drop=True)

    # Derive cost per item
    monthly['total_cpi'] = (monthly['total_nic'] / monthly['total_items']).round(4)

    logger.info(f"Monthly totals: {len(monthly)} months from {monthly['ds'].min().strftime('%Y-%m')} to {monthly['ds'].max().strftime('%Y-%m')}")
    return monthly


def fit_and_forecast(monthly, target_col, label, changepoint_scale):
    """
    Fit a Prophet model on a single target column and generate a forecast.

    Args:
        monthly           : DataFrame with ds and the target column
        target_col        : Column name to forecast (total_items, total_nic, total_cpi)
        label             : Human-readable label for logging
        changepoint_scale : Prophet changepoint_prior_scale — higher = more flexible

    Returns:
        DataFrame with ds, yhat, yhat_lower, yhat_upper columns
    """
    from prophet import Prophet

    # Prepare Prophet input — requires exactly two columns: ds and y
    prophet_df = monthly[['ds', target_col]].rename(columns={target_col: 'y'})

    # Initialise model
    # yearly_seasonality=True — captures annual prescribing patterns (e.g. March surge)
    # weekly/daily seasonality=False — data is monthly, not daily/weekly
    # interval_width — 80% CI
    # changepoints=['2022-01-01'] — explicitly marks the Sertraline genericisation
    # structural break so Prophet models it cleanly rather than auto-detecting it.
    model = Prophet(
        yearly_seasonality      =True,
        weekly_seasonality      =False,
        daily_seasonality       =False,
        changepoint_prior_scale =changepoint_scale,
        interval_width          =CONFIDENCE_INTERVAL,
        seasonality_mode        ='additive',
        changepoints            =['2022-01-01']
    )

    # Fit
    model.fit(prophet_df)
    logger.info(f"  {label}: model fitted on {len(prophet_df)} months of data.")

    # Generate future dates — monthly frequency, 12 months beyond the last data point
    future = model.make_future_dataframe(periods=FORECAST_PERIODS, freq='MS')
    forecast = model.predict(future)

    logger.info(f"  {label}: forecast generated for {FORECAST_PERIODS} months ahead.")

    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]


def validate_model(monthly, target_col, label, changepoint_scale):
    """
    Run walk-forward cross-validation and return the mean MAPE.
    Uses the last 12 months as a holdout — train on all prior months, predict 6 ahead.
    Returns MAPE as a percentage (e.g. 2.1 means 2.1%).
    """
    from prophet import Prophet
    from prophet.diagnostics import cross_validation, performance_metrics

    prophet_df = monthly[['ds', target_col]].rename(columns={target_col: 'y'})

    model = Prophet(
        yearly_seasonality      =True,
        weekly_seasonality      =False,
        daily_seasonality       =False,
        changepoint_prior_scale =changepoint_scale,
        interval_width          =CONFIDENCE_INTERVAL,
        seasonality_mode        ='additive',
        changepoints            =['2022-01-01']
    )

    model.fit(prophet_df)

    # Cross-validate: train on first 24 months, step 6 months, predict 6 months ahead
    cv_results = cross_validation(
        model,
        initial ='730 days',
        period  ='180 days',
        horizon ='180 days'
    )

    metrics = performance_metrics(cv_results)
    mape    = metrics['mape'].mean() * 100
    logger.info(f"  {label} MAPE: {mape:.2f}%")
    return round(mape, 2)


def build_forecast_table(monthly, fc_items, fc_nic, fc_cpi):
    """
    Combine the three Prophet forecasts into a single flat table.
    Adds actual values for the historical period and flags the forecast period.
    Clips negative forecast values to zero — items and cost cannot be negative.
    """
    # Rename forecast columns per measure
    items_out = fc_items.rename(columns={
        'yhat'      : 'items_forecast',
        'yhat_lower': 'items_lower',
        'yhat_upper': 'items_upper'
    })

    nic_out = fc_nic[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].rename(columns={
        'yhat'      : 'nic_forecast',
        'yhat_lower': 'nic_lower',
        'yhat_upper': 'nic_upper'
    })

    cpi_out = fc_cpi[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].rename(columns={
        'yhat'      : 'cpi_forecast',
        'yhat_lower': 'cpi_lower',
        'yhat_upper': 'cpi_upper'
    })

    # Merge all three forecasts on date
    combined = items_out.merge(nic_out, on='ds').merge(cpi_out, on='ds')

    # Add is_forecast flag
    last_actual = monthly['ds'].max()
    combined['is_forecast'] = combined['ds'] > last_actual

    # Merge actual values for the historical period
    actuals = monthly[['ds', 'total_items', 'total_nic', 'total_cpi']].rename(columns={
        'total_items': 'actual_items',
        'total_nic'  : 'actual_nic',
        'total_cpi'  : 'actual_cpi'
    })
    combined = combined.merge(actuals, on='ds', how='left')

    # Clip negative values — items and cost cannot be negative
    for col in ['items_forecast', 'items_lower', 'nic_forecast', 'nic_lower', 'cpi_forecast', 'cpi_lower']:
        combined[col] = combined[col].clip(lower=0)

    # Add year_month string column for Power BI relationship to Calendar table
    combined['year_month'] = combined['ds'].dt.strftime('%Y-%m')

    # Round all numeric columns to 2 decimal places
    numeric_cols = [c for c in combined.columns if c not in ['ds', 'year_month', 'is_forecast']]
    combined[numeric_cols] = combined[numeric_cols].round(2)

    # Final column order — mirrors the structure of other pipeline outputs
    combined = combined[[
        'year_month',
        'actual_items', 'actual_nic', 'actual_cpi',
        'items_forecast', 'items_lower', 'items_upper',
        'nic_forecast',   'nic_lower',   'nic_upper',
        'cpi_forecast',   'cpi_lower',   'cpi_upper',
        'is_forecast'
    ]]

    return combined


def print_forecast_summary(forecast_df, mape_items, mape_nic, mape_cpi):
    """Print a clean summary table of the 12-month forecast to the console."""
    future_rows = forecast_df[forecast_df['is_forecast']].copy()

    print()
    print("=" * 90)
    print("12-MONTH FORECAST SUMMARY")
    print("=" * 90)
    print(f"{'Month':<10} {'Items (M)':>10} {'Lower':>8} {'Upper':>8} {'Cost (£M)':>11} {'Lower':>9} {'CPI (£)':>9}")
    print("-" * 90)

    for _, row in future_rows.iterrows():
        print(
            f"{row['year_month']:<10}"
            f"{row['items_forecast']/1e6:>10.2f}"
            f"{row['items_lower']/1e6:>8.2f}"
            f"{row['items_upper']/1e6:>8.2f}"
            f"{row['nic_forecast']/1e6:>11.2f}"
            f"{row['nic_lower']/1e6:>9.2f}"
            f"{row['cpi_forecast']:>9.2f}"
        )

    print("-" * 90)
    total_items = future_rows['items_forecast'].sum()
    total_nic   = future_rows['nic_forecast'].sum()
    avg_cpi     = total_nic / total_items
    print(
        f"{'TOTAL/AVG':<10}"
        f"{total_items/1e6:>10.2f}"
        f"{'':>8}{'':>8}"
        f"{total_nic/1e6:>11.2f}"
        f"{'':>9}"
        f"{avg_cpi:>9.2f}"
    )
    print("=" * 90)
    print(f"Model: Facebook Prophet  |  Confidence: {int(CONFIDENCE_INTERVAL * 100)}%  |  Changepoint: 2022-01")
    print(f"MAPE — Items: {mape_items:.2f}%  |  Cost: {mape_nic:.2f}%  |  Cost Per Item: {mape_cpi:.2f}%")
    print("=" * 90)


def main():
    logger.info("=" * 60)
    logger.info("NHS PCA FORECAST — STARTING")
    logger.info(f"Input  : {INPUT_PATH}")
    logger.info(f"Output : {OUTPUT_PATH}")
    logger.info(f"Periods: {FORECAST_PERIODS} months  |  CI: {int(CONFIDENCE_INTERVAL * 100)}%")
    logger.info("=" * 60)

    # ── Step 1: Load staged data ──────────────────────────────────────────────
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"Staged file not found: {INPUT_PATH}\n"
            f"Run processor.py first to generate this file."
        )

    logger.info("Loading staged data...")
    df = pd.read_csv(INPUT_PATH)
    logger.info(f"Loaded {len(df):,} rows from staged CSV.")

    # ── Step 2: Build monthly national totals ─────────────────────────────────
    logger.info("Aggregating to monthly national totals...")
    monthly = build_monthly_totals(df)

    # ── Step 3: Validate models and report MAPE ───────────────────────────────
    # Validation runs before fitting the final model to surface accuracy early.
    # Items uses conservative changepoint scale — trend is smooth and steady.
    # NIC and CPI use higher scale — the 2022 genericisation was a sharp break.
    logger.info("Validating models (cross-validation)...")
    mape_items = validate_model(monthly, 'total_items', 'Items',         changepoint_scale=0.05)
    mape_nic   = validate_model(monthly, 'total_nic',   'Cost (NIC)',    changepoint_scale=0.30)
    mape_cpi   = validate_model(monthly, 'total_cpi',   'Cost Per Item', changepoint_scale=0.30)

    # ── Step 4: Fit final models and generate forecasts ───────────────────────
    logger.info("Fitting final models and generating forecasts...")
    fc_items = fit_and_forecast(monthly, 'total_items', 'Items',         changepoint_scale=0.05)
    fc_nic   = fit_and_forecast(monthly, 'total_nic',   'Cost (NIC)',    changepoint_scale=0.30)
    fc_cpi   = fit_and_forecast(monthly, 'total_cpi',   'Cost Per Item', changepoint_scale=0.30)

    # ── Step 5: Build combined forecast table ─────────────────────────────────
    logger.info("Building combined forecast table...")
    forecast_df = build_forecast_table(monthly, fc_items, fc_nic, fc_cpi)
    logger.info(f"Forecast table: {len(forecast_df)} rows ({(~forecast_df['is_forecast']).sum()} historical + {forecast_df['is_forecast'].sum()} forecast)")

    # ── Step 6: Save forecast CSV ─────────────────────────────────────────────
    forecast_df.to_csv(OUTPUT_PATH, index=False)
    logger.info(f"Forecast saved: {len(forecast_df):,} rows → {OUTPUT_PATH}")
    logger.info("Next step: run loader.py to load into MySQL.")

    # ── Step 7: Print summary ─────────────────────────────────────────────────
    print_forecast_summary(forecast_df, mape_items, mape_nic, mape_cpi)

    logger.info("=" * 60)
    logger.info("FORECAST COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()