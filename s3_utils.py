import boto3
import pandas as pd
from io import StringIO
import streamlit as st
from botocore.exceptions import ClientError


def get_s3_client():
    """Create and return an S3 client using credentials from secrets"""
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
            region_name=st.secrets.get("AWS_REGION", "ap-south-1")
        )
        return s3_client
    except Exception as e:
        raise Exception(f"Failed to create S3 client: {str(e)}")


def read_csv_from_s3(bucket_name, file_key):
    """Read a CSV file from S3 and return it as a pandas DataFrame"""
    try:
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        csv_content = response['Body'].read().decode('utf-8')
        df = pd.read_csv(StringIO(csv_content), low_memory=False)
        return df
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise FileNotFoundError(
                f"File {file_key} not found in bucket {bucket_name}")
        raise Exception(f"Error reading file from S3: {str(e)}")


def save_df_to_s3(df, bucket_name, file_key):
    """Save a pandas DataFrame to S3 as a CSV file"""
    try:
        s3_client = get_s3_client()
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=csv_buffer.getvalue()
        )
    except Exception as e:
        raise Exception(f"Error saving file to S3: {str(e)}")


def check_file_exists_in_s3(bucket_name, file_key):
    """Check if a file exists in S3"""
    try:
        s3_client = get_s3_client()
        s3_client.head_object(Bucket=bucket_name, Key=file_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise Exception(f"Error checking file existence in S3: {str(e)}")


def list_files_in_s3(bucket_name, prefix=""):
    """List files in an S3 bucket with an optional prefix"""
    try:
        s3_client = get_s3_client()
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )

        if 'Contents' in response:
            return [item['Key'] for item in response['Contents']]
        return []
    except Exception as e:
        raise Exception(f"Error listing files in S3: {str(e)}")
