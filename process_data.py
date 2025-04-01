import pandas as pd
import streamlit as st
from s3_utils import read_csv_from_s3, save_df_to_s3, check_file_exists_in_s3

# S3 configuration
S3_BUCKET = st.secrets["S3_BUCKET"]
S3_PREFIX = st.secrets["S3_PREFIX"]


def preprocess_sales_data():
    """Preprocess sales data for the dashboard"""
    # Load sales data from S3
    sales_data = read_csv_from_s3(
        S3_BUCKET, f"{S3_PREFIX}merged_sales_data.csv")

    # Convert Year to string for consistent handling
    sales_data['Year'] = sales_data['Year'].astype(str)

    # Ensure numeric columns are properly formatted
    numeric_cols = ['MTD SALES', 'MTD BILLS', 'MTD ABV']
    for col in numeric_cols:
        if col in sales_data.columns:
            sales_data[col] = pd.to_numeric(sales_data[col], errors='coerce')

    # Create month order for sorting
    month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    sales_data['Month_Num'] = sales_data['Month'].apply(
        lambda x: month_order.index(x) + 1 if x in month_order else 0)

    # Save processed data to S3
    save_df_to_s3(sales_data, S3_BUCKET,
                  f"{S3_PREFIX}processed_sales_data.csv")

    return sales_data


def process_service_data_chunks():
    """Process service data in chunks due to its large size"""
    processed_file_key = f"{S3_PREFIX}processed_service_data.csv"

    # Check if processed file already exists in S3
    if check_file_exists_in_s3(S3_BUCKET, processed_file_key):
        return {"status": "exists", "file": processed_file_key}

    # If we need to process the file
    chunk_size = 100000  # Adjust based on your available memory

    # Initialize data structures to hold aggregated data
    service_summary = pd.DataFrame()

    # Read and process file in chunks from S3
    raw_data = read_csv_from_s3(
        S3_BUCKET, f"{S3_PREFIX}merged_service_data.csv")

    # Process chunks
    for i in range(0, len(raw_data), chunk_size):
        chunk = raw_data.iloc[i:i + chunk_size].copy()

        # Extract year from Sale Date
        chunk['Year'] = chunk['Sale Date'].str.split('-').str[-1]

        # Categorize as product or service
        chunk['Category'] = chunk['Item Type'].apply(
            lambda x: 'Product' if x == 'Product' else 'Service'
        )

        # Further categorize services
        def categorize_service(row):
            if row['Category'] != 'Service':
                return 'Product'

            category = str(row.get('Item Category', '')).lower()
            subcategory = str(row.get('Item Subcategory', '')).lower()
            item_name = str(row.get('Item Name', '')).lower()

            if any(x in category for x in ['hair', 'haircut', 'color']) or \
               any(x in subcategory for x in ['hair', 'cut', 'color']) or \
               any(x in item_name for x in ['hair', 'cut', 'color', 'style', 'blowdry']):
                return 'Hair'
            elif any(x in category for x in ['facial', 'skin', 'face']) or \
                    any(x in subcategory for x in ['facial', 'skin', 'cleanup']) or \
                    any(x in item_name for x in ['facial', 'skin', 'cleanup']):
                return 'Skin'
            elif any(x in category for x in ['spa', 'massage', 'therapy']) or \
                    any(x in subcategory for x in ['spa', 'massage', 'therapy']) or \
                    any(x in item_name for x in ['spa', 'massage', 'therapy']):
                return 'SPA'
            else:
                return 'Other Services'

        chunk['Service_Type'] = chunk.apply(categorize_service, axis=1)

        # Preserve selected original columns for detailed filtering
        columns_to_preserve = [
            'Center Name', 'Year', 'Category', 'Service_Type',
            'Item Category', 'Item Subcategory', 'Business Unit'
        ]

        preserved_columns = []
        for col in columns_to_preserve:
            if col in chunk.columns:
                preserved_columns.append(col)

        # Aggregate data by center, year, category and other preserved columns
        agg_chunk = chunk.groupby(preserved_columns)['Sales Collected (Inc.Tax)'].agg(
            ['sum', 'count']).reset_index()

        # Append to our main dataframe
        service_summary = pd.concat([service_summary, agg_chunk])

    # Further aggregate the summary data
    group_columns = [
        col for col in service_summary.columns if col not in ['sum', 'count']]
    service_summary = service_summary.groupby(group_columns).agg({
        'sum': 'sum',
        'count': 'sum'
    }).reset_index()

    # Rename columns
    service_summary.rename(columns={
        'sum': 'Total_Sales',
        'count': 'Transaction_Count'
    }, inplace=True)

    # Save aggregated data to S3
    save_df_to_s3(service_summary, S3_BUCKET, processed_file_key)

    return {"status": "processed", "file": processed_file_key}


def load_processed_service_data():
    """Load the preprocessed service data from S3"""
    try:
        if check_file_exists_in_s3(S3_BUCKET, f"{S3_PREFIX}processed_service_data.csv"):
            service_data = read_csv_from_s3(
                S3_BUCKET, f"{S3_PREFIX}processed_service_data.csv")

            # Make sure Year is string for consistent handling
            if 'Year' in service_data.columns:
                service_data['Year'] = service_data['Year'].astype(str)

            return service_data
        else:
            # Return empty DataFrame with expected columns if file doesn't exist
            return pd.DataFrame(columns=[
                'Center Name', 'Year', 'Category', 'Service_Type',
                'Item Category', 'Item Subcategory', 'Business Unit',
                'Total_Sales', 'Transaction_Count'
            ])
    except Exception as e:
        print(f"Error loading service data: {str(e)}")
        return pd.DataFrame()


def map_salon_to_center():
    """Create a mapping between salon names and center names for comparison"""
    # This is a placeholder function that would create a mapping
    # between salon names in sales data and center names in service data
    # for more accurate comparisons between the two datasets

    # For now, return a simple mapping (this should be customized based on actual data)
    mapping = {
        'T NAGAR': 'T. NAGAR CENTER',
        'ADYAR': 'ADYAR CENTER',
        # Add more mappings as needed
    }

    return mapping


if __name__ == "__main__":
    print("Processing sales data...")
    preprocess_sales_data()

    print("Processing service data in chunks...")
    result = process_service_data_chunks()
    print(f"Service data processing status: {result['status']}")

    print("Data processing complete!")
