#backend/data_loaders.py
import pandas as pd
import numpy as np
import glob
import os

# -----------------------------
# Kaggle loaders
# -----------------------------
def load_kaggle_generation(path):
    df = pd.read_csv(path, parse_dates=["DATE_TIME"], dayfirst=True)
    df = df.sort_values("DATE_TIME")
    agg = df.groupby("DATE_TIME").agg({
        "DC_POWER": "sum",
        "AC_POWER": "sum"
    }).reset_index()
    # 1-minute resolution for memory efficiency
    agg = agg.set_index("DATE_TIME").resample("1min").interpolate()
    return agg.rename(columns={"DC_POWER": "dc_kW", "AC_POWER": "ac_kW"})


def load_kaggle_weather(path):
    df = pd.read_csv(path, parse_dates=["DATE_TIME"], dayfirst=True)
    df = df.sort_values("DATE_TIME")
    agg = df.groupby("DATE_TIME").agg({
        "AMBIENT_TEMPERATURE": "mean",
        "MODULE_TEMPERATURE": "mean",
        "IRRADIATION": "mean"
    }).reset_index()
    agg = agg.set_index("DATE_TIME").resample("1min").interpolate()
    return agg.rename(columns={
        "AMBIENT_TEMPERATURE": "ambient_C",
        "MODULE_TEMPERATURE": "module_C",
        "IRRADIATION": "irradiance"
    })

# -----------------------------
# Mendeley loaders
# -----------------------------
def load_mendeley_month(path):
    xls = pd.ExcelFile(path)

    if "Sheet1" in xls.sheet_names:
        df = pd.read_excel(path, sheet_name="Sheet1", header=1)
        if "Unnamed: 0" in df.columns:
            df = df.rename(columns={"Unnamed: 0": "time"})
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time").sort_index()
        rename_map = {
            "NLDC_DEMAND|P": "demand_MW",
            "ALL_IND_SOLAR|P": "solar_MW",
            "ALL_INDIA_WIND|P": "wind_MW",
            "Solar+Wind": "solar_wind_MW",
            "Solar": "solar_MW_cleaned"
        }
        df = df.rename(columns=rename_map)
        out = pd.DataFrame(index=df.index)
        if "demand_MW" in df.columns:
            out["demand_kW"] = df["demand_MW"].astype(float) * 1000.0
        if "solar_wind_MW" in df.columns:
            out["solar_wind_kW"] = df["solar_wind_MW"].astype(float) * 1000.0
        if "solar_MW" in df.columns:
            out["solar_kW"] = df["solar_MW"].astype(float) * 1000.0
        if "wind_MW" in df.columns:
            out["wind_kW"] = df["wind_MW"].astype(float) * 1000.0
        if "solar_MW_cleaned" in df.columns:
            out["solar_cleaned_kW"] = df["solar_MW_cleaned"].astype(float) * 1000.0

    elif "Report" in xls.sheet_names:
        df = pd.read_excel(path, sheet_name="Report", header=0)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Timestamp"])
        df = df.set_index("Timestamp").sort_index()
        out = pd.DataFrame(index=df.index)
        if "Demand (MW)" in df.columns:
            out["demand_kW"] = df["Demand (MW)"].astype(float) * 1000.0
        if "Solar (MW)" in df.columns:
            out["solar_kW"] = df["Solar (MW)"].astype(float) * 1000.0
        if "Wind (MW)" in df.columns:
            out["wind_kW"] = df["Wind (MW)"].astype(float) * 1000.0
        if "Total Generation (MW)" in df.columns:
            out["total_gen_kW"] = df["Total Generation (MW)"].astype(float) * 1000.0

    else:
        raise ValueError(f"No recognized sheet found in {path}: {xls.sheet_names}")

    # Resample to 1min for memory efficiency
    out = out.resample("1min").interpolate()
    return out


def load_mendeley_all(folder_path, year=None):
    all_files = glob.glob(os.path.join(folder_path, "*.xlsx"))
    dfs = []
    for f in sorted(all_files):
        try:
            df = load_mendeley_month(f)
            if year:
                df = df[df.index.year == int(year)]
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            print(f"Skipping {f}: {e}")
    return pd.concat(dfs).sort_index() if dfs else pd.DataFrame()

# -----------------------------
# Alignment (Option B: relative rescaling)
# -----------------------------
def resample_align_relative(pv_df, demand_df, weather_df=None):
    """
    Align PV, demand, and optional weather data by relative index (force same length),
    and normalize all numeric columns (PV, demand, weather) to 0-1 for RL.

    Returns:
        pv_series_normalized, demand_series_normalized, price_array, weather_normalized (or None)
    """

    # Ensure datetime index
    if not isinstance(pv_df.index, pd.DatetimeIndex):
        pv_df = pv_df.set_index("DATE_TIME")
    if not isinstance(demand_df.index, pd.DatetimeIndex):
        demand_df = demand_df.set_index("DATE_TIME")
    if weather_df is not None and not isinstance(weather_df.index, pd.DatetimeIndex):
        weather_df = weather_df.set_index("DATE_TIME")

    # Resample all to 1-minute frequency
    pv_df = pv_df.resample("1min").interpolate()
    demand_df = demand_df.resample("1min").interpolate()
    if weather_df is not None:
        weather_df = weather_df.resample("1min").interpolate()

    # Force relative alignment by truncating to minimum length
    min_len = min(len(pv_df), len(demand_df))
    pv_df = pv_df.iloc[:min_len]
    demand_df = demand_df.iloc[:min_len]
    if weather_df is not None:
        weather_df = weather_df.iloc[:min_len]

    # Interpolate numeric columns separately
    pv_numeric_cols = pv_df.select_dtypes(include=[np.number]).columns
    pv_df[pv_numeric_cols] = pv_df[pv_numeric_cols].interpolate()

    demand_numeric_cols = demand_df.select_dtypes(include=[np.number]).columns
    demand_df[demand_numeric_cols] = demand_df[demand_numeric_cols].interpolate()

    if weather_df is not None:
        weather_numeric_cols = weather_df.select_dtypes(include=[np.number]).columns
        weather_df[weather_numeric_cols] = weather_df[weather_numeric_cols].interpolate()

    # Normalize PV
    pv_col = "ac_kW" if "ac_kW" in pv_df.columns else "dc_kW"
    pv_series_normalized = (pv_df[pv_col] - pv_df[pv_col].min()) / (
        pv_df[pv_col].max() - pv_df[pv_col].min() + 1e-8
    )

    # Normalize demand
    demand_series_normalized = (demand_df["demand_kW"] - demand_df["demand_kW"].min()) / (
        demand_df["demand_kW"].max() - demand_df["demand_kW"].min() + 1e-8
    )

    # Normalize weather if provided
    if weather_df is not None:
        weather_numeric_cols = weather_df.select_dtypes(include=[np.number]).columns
        weather_normalized = (weather_df[weather_numeric_cols] - weather_df[weather_numeric_cols].min()) / (
            weather_df[weather_numeric_cols].max() - weather_df[weather_numeric_cols].min() + 1e-8
        )
    else:
        weather_normalized = None

    # Price array (example: peak hours 18-22h = 7, else 3)
    hours = pv_df.index.hour
    price_array = np.where((hours >= 18) & (hours <= 22), 7.0, 3.0)

    return pv_series_normalized.values, demand_series_normalized.values, price_array, weather_normalized
