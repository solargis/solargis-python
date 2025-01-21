# Quickstart guide

1. Install required libs in `requirements.txt`
2. Get your API token.
3. Create a file `local_secrets.py` with contents like this: `token = "<your_API_token>"`
4. Run jupyter notebook server
5. Import required assets 
    ```py
    from sg_api_client import SG2APIClient
    from local_secrets import token
    ```
6. Try obtaining some data, e.g.
    ```py
    client = SGAPIClient(token, dest_folder="/where/you/want/save/your/data")
    client.add_request(site_name="Austria", lat=48.275231, long=14.26934, utc_offset="+01:00")
    client.add_request(site_name="Mosambique", lat=15.169717, long=39.253761, utc_offset="+02:00")
    client.add_request(site_name="Afghanistan", lat=37.095622, long=70.557353, utc_offset="+04:30")
    datasets = await client.retrieve_data()
    s```

# Using outside Jupyter notebooks

If you want to run the code outside Jupyter notebook, you need to import `asyncio` lib and call the main function as `asyncio.run(client.retrieve_data())`.


Alternatively, you can build your own evaluation routines asynchronously and use `await` - if you choose this way, you probably know what to do.