from supabase import create_client
import pandas as pd
import streamlit as st

# Supabase configuration from secrets


@st.cache_resource
def get_supabase_client():
    """Create and return a Supabase client using credentials from secrets"""
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
        client = create_client(supabase_url, supabase_key)
        return client
    except Exception as e:
        raise Exception(f"Failed to create Supabase client: {str(e)}")


def fetch_data_from_supabase(table_name="paulsons", query_params=None):
    """Fetch ALL data from Supabase table by year to handle large datasets"""
    try:
        client = get_supabase_client()
        all_data = []

        # Define years to fetch - include some buffer years to ensure we get all data
        years_to_fetch = list(range(2020, 2026))  # Fetch from 2020 to 2025
        print(f"Fetching data for years: {years_to_fetch}")

        # Fetch data for each year separately
        for year in years_to_fetch:
            year_data = []
            total_for_year = 0

            print(f"==== Fetching data for year {year} ====")

            # Use pagination for each year
            page_size = 10000
            page = 0

            while True:
                # Calculate range for this page
                start_range = page * page_size
                end_range = start_range + page_size - 1

                try:
                    # Create filter for this year
                    # Format: sale_date.gte.2023-01-01,sale_date.lt.2024-01-01
                    start_date = f"{year}-01-01"
                    end_date = f"{year+1}-01-01"

                    # Build the query with year filter
                    query = client.table(table_name).select("*")\
                        .gte("sale_date", start_date)\
                        .lt("sale_date", end_date)\
                        .range(start_range, end_range)

                    # Apply ordering if provided
                    if query_params and 'order' in query_params:
                        query = query.order(query_params['order'])

                    # Execute query
                    response = query.execute()

                    # Process results
                    if response.data and len(response.data) > 0:
                        page_count = len(response.data)
                        year_data.extend(response.data)
                        total_for_year += page_count

                        print(
                            f"Year {year}, Page {page+1}: {page_count} records (year total: {total_for_year})")

                        # If fewer records than page size, we've reached the end for this year
                        if page_count < page_size:
                            print(
                                f"Completed fetching data for year {year}, total: {total_for_year} records")
                            break
                    else:
                        # No more data for this year
                        print(
                            f"No more data for year {year} after page {page}")
                        break

                    # Move to next page
                    page += 1

                except Exception as e:
                    print(f"Error fetching year {year}, page {page}: {str(e)}")
                    # Try to continue with next page if possible
                    page += 1
                    if page > 50:  # Safety limit per year
                        print(
                            f"Reached maximum page retry limit for year {year}")
                        break

            # Add this year's data to the overall dataset
            if year_data:
                print(
                    f"Adding {len(year_data)} records for year {year} to dataset")
                all_data.extend(year_data)

        # Create DataFrame from all collected data
        if all_data:
            df = pd.DataFrame(all_data)
            print(
                f"Successfully fetched a total of {len(df)} records from all years")

            # Debug check - count records by year
            if 'sale_date' in df.columns:
                df['temp_year'] = pd.to_datetime(df['sale_date']).dt.year
                year_counts = df['temp_year'].value_counts().sort_index()
                print(
                    f"Years distribution in fetched data: {year_counts.to_dict()}")
                # Remove the temp column
                df = df.drop('temp_year', axis=1)

            return df
        else:
            print("No data found across all years")
            return pd.DataFrame()

    except Exception as e:
        print(f"Fatal error in fetch_data_from_supabase: {str(e)}")
        raise Exception(f"Error fetching data from Supabase: {str(e)}")


def save_data_to_supabase(df, table_name="paulsons"):
    """Save a pandas DataFrame to Supabase"""
    try:
        client = get_supabase_client()

        # Convert DataFrame to list of dictionaries
        records = df.to_dict(orient='records')

        # Insert or update data in Supabase
        response = client.table(table_name).upsert(records).execute()

        return response
    except Exception as e:
        raise Exception(f"Error saving data to Supabase: {str(e)}")
