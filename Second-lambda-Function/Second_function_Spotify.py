import json
import boto3
import pandas as pd
import pyarrow.parquet as pq
from io import BytesIO
from sqlalchemy import create_engine
from botocore.exceptions import ClientError

# Initialize Boto3 clients
s3_client = boto3.client('s3')  # S3 client for accessing files in S3
secrets_manager_client = boto3.client('secretsmanager')  # Secrets Manager client for secure credentials retrieval

def get_redshift_credentials(secret_name):
    """
    Retrieve Redshift credentials securely from AWS Secrets Manager.

    Parameters:
        secret_name (str): The name of the secret in Secrets Manager.

    Returns:
        tuple: A tuple containing Redshift username and password.
    """
    try:
        response = secrets_manager_client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        return secret['username'], secret['password']
    except ClientError as e:
        print(f"Error retrieving secret: {e}")
        raise

def handler(event, context):
    """
    Lambda handler function triggered by S3 events, processing Parquet files and loading data to Redshift.

    Parameters:
        event (dict): Event data containing S3 file information.
        context (LambdaContext): Runtime information provided by AWS Lambda.
    """
    secret_name = '<your_secret_name>'  # Secrets Manager name for Redshift credentials
    
    try:
        # Retrieve Redshift credentials
        username, password = get_redshift_credentials(secret_name)

        # Process each record in the event
        for record in event['Records']:
            body = json.loads(record['body'])
            s3_info = body['Records'][0]['s3']
            bucket_name = s3_info['bucket']['name']
            object_key = s3_info['object']['key']

            # Check if the file is a Parquet file in the designated "stage-data" folder
            if object_key.endswith('.parquet') and 'stage-data/' in object_key:
                try:
                    # Download Parquet file from S3
                    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
                    parquet_data = response['Body'].read()
                    
                    # Read Parquet file into a DataFrame
                    table = pq.read_table(BytesIO(parquet_data))
                    df = table.to_pandas()

                    # Redshift connection setup
                    workgroup_name = 'spotify-data'
                    redshift_table_name = 'Spotify'

                    # Construct Redshift connection string
                    engine = create_engine(
                        f'redshift+psycopg2://{username}:{password}@{workgroup_name}.<your_string_connection>'
                    )

                    # Set column names to match Redshift table structure
                    df.columns = ['Id', 'Artist', 'Song_Name', 'Plays', 'Album', 'Duration', 'Release_Date']

                    # Upload data to Redshift table
                    df.to_sql(redshift_table_name, engine, index=False, if_exists='append', method='multi')
                
                except ClientError as e:
                    print(f"Error getting object from S3: {e}")
                    return {'statusCode': 500, 'body': json.dumps('Error downloading file from S3')}

    except ClientError as e:
        print(f"Error: {e}")
        return {'statusCode': 500, 'body': json.dumps('Error during execution')}
    
    # Successful processing response
    return {
        'statusCode': 200,
        'body': json.dumps('File processed successfully!')
    }
