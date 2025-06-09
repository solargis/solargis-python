# Solargis API Client
A simple python client for communication with Solargis API. It submits a request, 
repeatedly checks for its status until it's done and (on success) saves the downloaded data to your device. It supports 

 1. Solargis API for time-series (TS) data and
 2. Solargis API for typical meteorological year (TMY) data.

# Quickstart guide

1. Install required libs: `pip install -r requirements.txt`
2. [Get your API token](https://kb.solargis.com/docs/generate-api-tokens). Note that TMY and TS API have different tokens.
3. Create a file `local_secrets.py` with your activated token(s): 
    ```py
    token_ts = "<your_TS_API_token>"
    token_tmy = "<your_TMY_API_token>"
    ```
4. Run jupyter notebook server
5. Try TMY  or TS integration python API call - see below.


# Typical Meteorological Year API Quickstart

The asynchronous nature of both the API and the client allows processing multiple
requests in parallel. In a simple scenario, you can specify the sites using only
names and coordinates `(lat, lon)`. This code will retrieve TMY data for 3 sites and
save them into 3 different `.zip` files.

```py
from tmy_api_client import TMYAPIClient
from local_secrets import token_tmy

tmy_client = TMYAPIClient(token=token_tmy, dest_folder="/where/you/want/save/your/data")
tmy_client.add_request(site_name="Austria", lat=48.275231, long=14.26934)
tmy_client.add_request(site_name="Mosambique", lat=15.169717, long=39.253761)
tmy_client.add_request(site_name="Afghanistan", lat=37.095622, long=70.557353)
await tmy_client.retrieve_all_data()
```

 > Note: if you want to run this code outside Jupyter notebook, see [Using outside Jupyter notebooks](using-outside-jupyter-notebooks).

 > Note: The time zone is automatically determined from coordinates and may differ from the actual political time zone. Always check file header for time zone info.

In the `add_request()` method, you can specify any subset of [parameters for the TMY request](https://kb.solargis.com/apidocs/generate-tmy-data).

If you wish to process the data right away, you can also call the `retreive_data` method with `create_dataframes=True`:
```py
tmy_datasets = await tmy_client.retrieve_data(create_dataframes=True)
```
`tmy_datasets` (as well as `tmy_client.datasets`) now contains a dictionary of `pandas` data frames with the TMY data. The keys are the `site_name`s specified in `add_request`. 

 > Note: with `create_dataframes=True`, the client will always download the data also in SOLARGIS_JSON format. No additional cost will be charged. 

For processing the datasets directly, you might prefer using a python script rather than a notebook - see [Using outside Jupyter notebooks](using-outside-jupyter-notebooks).

# Time Series API Quickstart
Time Series API calls are similar to (TMY API calls)[typical-meteorological-year-api-quickstart]. There are a few notable differences, though: 
 1. The [TS requests are different](https://kb.solargis.com/apidocs/get-requestid-for-timeseries-data). 
 2. The `pandas` data frames are always created.
 3. The results are saved with data (csv) and metadata (json) separately and uncompressed.
 4. The UTC offset can be specified in the request. The default is zero (time stamps in UTC).


```py
from ts_api_client import TSAPIClient
from local_secrets import token_ts

ts_client = TSAPIClient(token_ts, dest_folder="/where/you/want/save/your/data")
ts_client.add_request(site_name="Austria", lat=48.275231, long=14.26934, utc_offset="+01:00")
ts_client.add_request(site_name="Mosambique", lat=15.169717, long=39.253761, utc_offset="+02:00")
ts_client.add_request(site_name="Afghanistan", lat=37.095622, long=70.557353, utc_offset="+04:30")
datasets = await ts_client.retrieve_all_data()
```
 > Note: if you want to run this code outside Jupyter notebook, see [Using outside Jupyter notebooks](using-outside-jupyter-notebooks).

# Using outside Jupyter notebooks

If you want to run the code outside Jupyter notebook, you need to import `asyncio` lib and call the main function as `asyncio.run(client.retrieve_all_data())` as follows:

```py
import asyncio

from local_secrets import token_tmy
from tmy_api_client import TMYAPIClient

client = TMYAPIClient(token_tmy, dest_folder="/where/you/want/save/your/data")
client.add_request(site_name="Austria", lat=48.275231, long=14.26934)
datasets = asyncio.run(client.retrieve_all_data())
```


Alternatively, you can build your own evaluation routines asynchronously. This way, the program doesn't need to 
wait until all requests are answered and can start data processing as soon as data for any request is available. 

```py
import asyncio
import pandas as pd

from local_secrets import token_ts
from ts_api_client import TSAPIClient

def process_data(name: str, dataset: pd.Dataframe, metadata: dict):
    ... # your custom function for data processing

async def main(client: TSAPIClient):
    async for name, dataset, metadata in client.retrieve_data():
        process_data(name, dataset, metadata)

client = TSAPIClient(token_ts, dest_folder="/where/you/want/save/your/data")
client.add_request(site_name="Austria", lat=48.275231, long=14.26934, utc_offset="+01:00")

asyncio.run(main(client))
```


# Specifying module mounting in TS requests

Module mounting is specified in the `gtiConfiguration` section (GTI = Global Tilted Irradiance). See [solargis schemas](https://github.com/solargis/schemas/tree/main/examples/requests/public/ts_api) repository for more examples.

```py
gti_configuration = {
  "layout":{
    "azimuth":180,
    "mounting":{
      "type":"FIXED_ONE_ANGLE",
      "tilt":30
    }
  }
}

client = TSAPIClient(
    token, 
    dest_folder="/where/you/want/save/your/data"
)
client.add_request(
   site_name="Austria",
   parameters=["GHI", "GTI"],
   lat=48.275231,
   long=14.26934,
   terrainShadig=True,
   utc_offset="+01:00",
   time_step="P1Y",
   gtiConfiguration=gti_configuration
)
```
