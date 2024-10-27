import os
import boto3
import csv
from datetime import datetime
import json
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

def handler(event, context):
    """
    Lambda entry point. Retrieves Spotify credentials from AWS Secrets Manager, 
    gets top tracks data from Spotify, and saves it as a CSV file to an S3 bucket.
    """
    # Fetch Spotify credentials from AWS Secrets Manager
    secrets = get_secrets('<your_secret>')
    client_id = secrets['<your_secret_id>']
    client_secret = secrets['<your_secret_value>']

    # Get top tracks data
    top_tracks = get_top_tracks(client_id, client_secret)

    # Generate a CSV filename with the current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    file_name = f"spotify-test-{current_date}.csv"

    # Save data to S3
    save_to_s3(top_tracks, '<your_bucket>', f"raw-data/{file_name}")

    return {
        'statusCode': 200,
        'body': f"File {file_name} has been uploaded to <your_bucket>/raw-data."
    }

def get_secrets(secret_name):
    """
    Retrieve secrets from AWS Secrets Manager.
    
    Parameters:
        secret_name (str): The name of the secret in AWS Secrets Manager.

    Returns:
        dict: A dictionary containing the secrets.
    """
    session = boto3.Session()
    client = session.client('secretsmanager')
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error getting secrets: {e}")
        raise  # Propagate error to Lambda handler

def get_top_tracks(client_id, client_secret, limit=50):
    """
    Fetches the top tracks from Spotify using client credentials.
    
    Parameters:
        client_id (str): Spotify client ID.
        client_secret (str): Spotify client secret.
        limit (int): The number of tracks to retrieve (default is 50).
    
    Returns:
        list[dict]: A list of dictionaries containing track information.
    """
    client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    top_tracks = spotify.search(q='all', type='track', limit=limit)
    track_info_list = []
    for track in top_tracks['tracks']['items']:
        track_info = {
            'id': track['id'],
            'artist': track['artists'][0]['name'],
            'song_name': track['name'],
            'plays': track['popularity'],
            'album': track['album']['name'],
            'duration': track['duration_ms'] // 1000,  # Duration in seconds
            'release_date': track['album']['release_date']
        }
        track_info_list.append(track_info)
    
    return track_info_list

def save_to_s3(data, bucket_name, file_name):
    """
    Saves the data as a CSV file in an S3 bucket.
    
    Parameters:
        data (list[dict]): The data to be saved.
        bucket_name (str): The name of the S3 bucket.
        file_name (str): The name of the file to be saved.
    """
    csv_file = f'/tmp/{file_name.split("/")[-1]}'  # Local path for CSV creation
    with open(csv_file, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    # Upload CSV to S3
    s3_client = boto3.client('s3')
    s3_client.upload_file(csv_file, bucket_name, file_name)
    print(f"File {file_name} has been uploaded to {bucket_name}.")
