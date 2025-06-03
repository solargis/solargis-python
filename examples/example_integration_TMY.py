from local_secrets import (
    token_tmy_integration,
)  # for this you need to have Pro integration subscription
import pandas as pd

from tmy_api_client import tmy


SUBHOURLY_15MIN = "PT15M"
HOURLY = "PT60M"

df: pd.DataFrame = tmy(
    token_tmy_api=token_tmy_integration,
    lat=48.61259,
    long=20.827079,
    time_step=HOURLY,
    integration_api_call=True,
    tmyScenario="P50",
    siteName="Pro example Site",
    fileLabel="pro_01",
    outputFormats=["SOLARGIS_CSV", "SOLARGIS_JSON", "SAM", "HELIOSCOPE"],
)
