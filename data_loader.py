import streamlit as st
import pandas as pd
from supabase_utils import fetch_data_from_supabase
from s3_utils import check_file_exists_in_s3, read_file_from_s3
import datetime

# Load configuration from secrets
S3_BUCKET = st.secrets["S3_BUCKET"]
S3_PREFIX = st.secrets["S3_PREFIX"]
DATA_REFRESH_INTERVAL = st.secrets.get("DATA_REFRESH_INTERVAL", 3600)


@st.cache_data(ttl=DATA_REFRESH_INTERVAL)
def load_sales_data():
    """Load sales data from Supabase"""
    try:
        # Display status
        with st.spinner("Loading sales data..."):
            sales_data = fetch_data_from_supabase(table_name="paulsons")

            if not sales_data.empty:
                # Clean and convert numeric columns
                numeric_cols = ['sales_collected_exc_tax', 'tax_collected', 'sales_collected_inc_tax',
                                'redeemed', 'collected_to_date', 'collected']
                for col in numeric_cols:
                    if col in sales_data.columns:
                        # First remove currency symbols and commas
                        sales_data[col] = sales_data[col].replace(
                            {'\$': '', '₹': '', ',': ''}, regex=True)
                        # Convert to numeric, coercing errors to NaN
                        sales_data[col] = pd.to_numeric(
                            sales_data[col], errors='coerce')

                # Convert sale_date to datetime with error handling
                sales_data['sale_date'] = pd.to_datetime(
                    sales_data['sale_date'], errors='coerce')

                # Drop rows with invalid sale_date
                sales_data = sales_data.dropna(subset=['sale_date'])

                # Extract Year and Month as strings
                sales_data['Year'] = sales_data['sale_date'].dt.year.astype(
                    str)
                sales_data['Month'] = sales_data['sale_date'].dt.strftime('%B')

                # Map columns to expected format for the dashboard
                sales_data['SALON NAMES'] = sales_data['center_name']
                sales_data['BRAND'] = sales_data['business_unit'].fillna(
                    'Other')

                # Create grouped data
                grouped_sales = create_grouped_sales(sales_data)

                # Mark as successfully loaded
                return {
                    "raw_data": sales_data,
                    "grouped_data": grouped_sales,
                    "success": True,
                    "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                return {
                    "raw_data": pd.DataFrame(),
                    "grouped_data": pd.DataFrame(),
                    "success": False,
                    "error": "No data returned from Supabase"
                }

    except Exception as e:
        return {
            "raw_data": pd.DataFrame(),
            "grouped_data": pd.DataFrame(),
            "success": False,
            "error": str(e)
        }


def create_grouped_sales(sales_data):
    """Create grouped sales data from raw sales data"""
    # Group by Year, Month, SALON NAMES, BRAND to calculate metrics
    grouped_sales = sales_data.groupby(['Year', 'Month', 'SALON NAMES', 'BRAND']).agg({
        'sales_collected_exc_tax': 'sum',
        'invoice_no': 'nunique'
    }).reset_index()

    # Rename columns to match expected format
    grouped_sales.rename(columns={
        'sales_collected_exc_tax': 'MTD SALES',
        'invoice_no': 'MTD BILLS'
    }, inplace=True)

    # Calculate Average Bill Value with error handling
    grouped_sales['MTD ABV'] = grouped_sales.apply(
        lambda row: row['MTD SALES'] /
        row['MTD BILLS'] if row['MTD BILLS'] > 0 else 0,
        axis=1
    )

    return grouped_sales


@st.cache_data(ttl=DATA_REFRESH_INTERVAL)
def load_leaves_data():
    """Load leaves data from the CSV file"""
    try:
        leaves_data_path = "dataset/2024_2025_Leaves.csv"
        leaves_data = pd.read_csv(leaves_data_path)
        leaves_data['Date'] = pd.to_datetime(
            leaves_data['Date'], errors='coerce')
        leaves_data = leaves_data.dropna(subset=['Date'])

        return {
            "data": leaves_data,
            "success": True,
            "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {
            "data": pd.DataFrame(),
            "success": False,
            "error": str(e)
        }


def load_all_data():
    """Load all required data for the dashboard"""
    # Load sales data
    sales_result = load_sales_data()

    # Load leaves data
    leaves_result = load_leaves_data()

    # Return combined results
    return {
        "sales": sales_result,
        "leaves": leaves_result,
        "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
