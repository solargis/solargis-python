from local_secrets import token_ts  # TODO you need to create this file & variable
from ts_api_client import TSAPIClient, historical_timeseries
import pandas as pd

SUBHOURLY_15MIN, HOURLY, MONTHLY, YEARLY= "PT15M", "PT60M", "P1M", "P1Y"

df: pd.DataFrame = historical_timeseries(
    token_timeseries_api=token_ts,
    lat=48.275231,
    long=14.26934,
    time_step=YEARLY,
    columns=["GHI", "DNI", "DIF", "GHI_NOSHD", "DNI_NOSHD", "DIF_NOSHD", "TEMP"],
)
