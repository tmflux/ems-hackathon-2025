from data_loaders import load_kaggle_generation, load_mendeley_all, load_kaggle_weather, align_pv_load_for_rl

pv_df = load_kaggle_generation("data/Kaggle/Plant_1_Generation_Data.csv")
load_df_all = load_mendeley_all("data/Mendeley/Electricity Demand, Solar and Wind Generation Data")
weather_df = load_kaggle_weather("data/Kaggle/Plant_1_Weather_Sensor_Data.csv")

pv_series, demand_series, weather_aligned, price_series = align_pv_load_for_rl(
    pv_df, load_df_all, weather_df, auto_shift_load=True
)

print(pv_series[:5], demand_series[:5], price_series[:5])
if weather_aligned is not None:
    print(weather_aligned.head())
