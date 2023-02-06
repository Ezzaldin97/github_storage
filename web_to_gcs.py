import os
from prefect import flow, task
import pandas as pd
from prefect_gcp.cloud_storage import GcsBucket
from pathlib import Path
from prefect.tasks import task_input_hash
from datetime import timedelta

@task(name = "fetch data", description = "Export/Get Data from Source",
      retries = 2, tags = ["Export", "Fetch", "RawData"], cache_key_fn = task_input_hash,
      cache_expiration = timedelta(hours = 1))
def fetch(url:str) -> pd.DataFrame:
    """
    Read Data File from Web as Pandas DataFrame...
    """
    df = pd.read_csv(url)
    return df

@task(log_prints=True, name = "Clean Data", description="clean some issues in data..",
      tags = ["CleanData"])
def clean(df:pd.DataFrame, color:str) -> pd.DataFrame:
    """
    Fix some issues in Data...
    """
    print(f"dataset shape before clean: {df.shape}")
    if color == "yellow":
        df.tpep_pickup_datetime = pd.to_datetime(df.tpep_pickup_datetime)
        df.tpep_dropoff_datetime = pd.to_datetime(df.tpep_dropoff_datetime)
    elif color == "green":
        df.lpep_pickup_datetime = pd.to_datetime(df.lpep_pickup_datetime)
        df.lpep_dropoff_datetime = pd.to_datetime(df.lpep_dropoff_datetime)
    df = df[df["passenger_count"] != 0]
    print(f"dataset shape after clean: {df.shape}")
    return df

@task(log_prints = True, name = "WriteToLocalEnv",
      description="Save Cleaned File as Parquet file to local Environment..",
      tags = ["LocalEnv", "WriteToLocal"])
def write_to_local(df:pd.DataFrame, color:str, dataset_file:str) -> Path:
    path = Path(f"./data_storage/{dataset_file}.parquet")
    df.to_parquet(path, compression="gzip")
    print(f"file {path} saved to Loacal Environment..")
    return path

@task(log_prints=True, name = "LoadToGCS", retries=1,
      description="Load File from Loacl Environment to GCS Bucket..",
      tags = ["Load", "GCS"])
def load_to_gcs(path:Path) -> None:
    """
    Load Data to GCS Bucket (DataLake)...
    """
    print(f"connecting to GCP-GCS Bucket..")
    gcs_bucket_block = GcsBucket.load("de-zoomcamp-2023")
    gcs_bucket_block.upload_from_path(from_path = path,  timeout=1200)
    print(f"file uploaded successfully to GCS..")

# this will run as sub-flow....  
@flow(name = "ETL from Web to GCS",
      description="Manage Workflow from Fetching data from Web, apply some Cleansing and Load to GCS Bucket.")
def etl_web_to_gcs(color:str, year:int, month:int) -> None:
    """
    Main ETL workflow Function...
    """
    dataset_file = f"{color}_tripdata_{year}-{month:02}"
    dataset_url = f"https://github.com/DataTalksClub/nyc-tlc-data/releases/download/{color}/{dataset_file}.csv.gz"
    df = fetch(dataset_url)
    df_cleaned = clean(df, color)
    local_path = write_to_local(df_cleaned, color=color, dataset_file=dataset_file)
    load_to_gcs(local_path)
    
#etl parent flow
@flow(name = "Parent Flow for ETL Workflow",
      description = "This Function Manages the Workflow of ETL Workflow to run for different parameters..")
def etl_parent_flow(months:list[int]=[1, 2], year=2020, colors:list[str]=["green"]):
    for color in colors:
        for month in months:
            etl_web_to_gcs(color, year, month)

if __name__ == "__main__":
    etl_parent_flow(months = [11], year = 2020, colors = ["green"])