from local_secrets import token_tmy # TODO this needs to be created!
from tmy_api_client import TMYAPIClient, tmy
import pandas as pd

SUBHOURLY_15MIN, HOURLY= "PT15M", "PT60M"

df: pd.DataFrame = tmy(
    token_tmy_api=token_tmy, lat=48.275231, long=14.26934, time_step=SUBHOURLY_15MIN
)
