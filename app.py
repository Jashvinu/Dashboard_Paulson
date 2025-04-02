import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
from process_data import preprocess_sales_data, load_processed_service_data
from s3_utils import read_csv_from_s3
import traceback


def format_indian_money(amount, format_type='full'):
    """
    Format money in Indian style with proper comma placement
    format_type: 'full' for regular formatting, 'lakhs' to convert to lakhs
    """
    if pd.isna(amount) or amount == 0:
        return "₹0"

    # Convert to lakhs if requested
    if format_type == 'lakhs':
        amount = amount / 100000
        formatted = f"₹{amount:.2f} Lakhs"
        return formatted

    def format_with_indian_commas(num):
        """Helper function to add commas in Indian number system"""
        s = str(int(round(num)))
        if len(s) > 3:
            last3 = s[-3:]
            rest = s[:-3]
            formatted_rest = ''
            for i in range(len(rest)-1, -1, -2):
                if i == 0:
                    formatted_rest = rest[i] + formatted_rest
                else:
                    formatted_rest = ',' + \
                        rest[max(i-1, 0):i+1] + formatted_rest
            result = formatted_rest + ',' + last3 if formatted_rest else last3
            # Remove the leftmost comma if it exists
            if result.startswith(','):
                result = result[1:]
            return result
        return s

    # Format with Indian style commas
    formatted_amount = format_with_indian_commas(amount)
    return f"₹{formatted_amount}"


# S3 configuration
S3_BUCKET = "extraa-files"
S3_KEY = "SALON/Extraction_Mini.csv"

# Enable memory optimization by default
MEMORY_OPTIMIZATION = True

# Set page configuration
st.set_page_config(
    page_title="Salon Business Dashboard",
    page_icon="💇",
    layout="wide"
)

# Title and description
st.title("Executive Business Dashboard")
st.markdown("### Sales and Service Performance Analytics")

# Initialize session state for data storage
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
    st.session_state.grouped_sales = None
    st.session_state.raw_sales_data = None
    st.session_state.last_refresh_time = None

# Load data
st.sidebar.title("Dashboard Controls")

# Add a more prominent button to clear cache and refresh data
refresh_col1, refresh_col2 = st.sidebar.columns([3, 1])
with refresh_col1:
    if st.button("🔄 Refresh All Data", use_container_width=True):
        # Clear all caches and session state
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state.data_loaded = False
        st.session_state.grouped_sales = None
        st.session_state.raw_sales_data = None
        st.success("All caches cleared! Refreshing complete dataset...")
        st.experimental_rerun()
with refresh_col2:
    st.write("")  # Empty space for alignment

# Add last refresh time indicator
if st.session_state.last_refresh_time:
    st.sidebar.caption(
        f"Last data refresh: {st.session_state.last_refresh_time}")
else:
    st.sidebar.caption(f"Last data refresh: Never")

# Completely disable caching to ensure fresh data every time
# @st.cache_data(ttl=60)  # Cache for just 1 minute


def load_data():
    # Load sales data from S3
    try:
        # Display status
        placeholder = st.empty()
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Display initial status
        status_text.info("Starting to fetch data from AWS S3...")

        try:
            # Fetch data from S3
            sales_data = read_csv_from_s3(S3_BUCKET, S3_KEY)

            # Use more efficient data types
            if MEMORY_OPTIMIZATION:
                # Convert object columns to categories where appropriate
                for col in sales_data.select_dtypes(['object']).columns:
                    # If column has less than 50% unique values
                    if sales_data[col].nunique() / len(sales_data) < 0.5:
                        sales_data[col] = sales_data[col].astype('category')

        except Exception as e:
            st.error(f"Failed to load data from S3: {str(e)}")
            st.info("Please check your S3 bucket permissions and configuration.")
            return pd.DataFrame(), pd.DataFrame()

        # Update status on completion
        if not sales_data.empty:
            progress_bar.progress(50)
            status_text.info(f"Processing {len(sales_data)} records...")

        # Clean and convert numeric columns
        numeric_cols = ['Sales Collected (Exc.Tax)', 'Tax Collected', 'Sales Collected (Inc.Tax)',
                        'Redeemed', 'Collected to Date', 'Collected']
        for col in numeric_cols:
            if col in sales_data.columns:
                # Convert to numeric, coercing errors to NaN
                sales_data[col] = pd.to_numeric(
                    sales_data[col], errors='coerce')

                # Optimize numeric columns
                if MEMORY_OPTIMIZATION:
                    # Downcast to smaller float type if possible
                    sales_data[col] = pd.to_numeric(
                        sales_data[col], downcast='float')

        progress_bar.progress(70)

        # Convert Sale Date to datetime with error handling
        sales_data['Sale Date'] = pd.to_datetime(
            sales_data['Sale Date'], errors='coerce')

        # Drop rows with invalid sale_date
        sales_data = sales_data.dropna(subset=['Sale Date'])

        # Extract Year and Month as strings
        sales_data['Year'] = sales_data['Sale Date'].dt.year.astype(str)
        sales_data['Month'] = sales_data['Sale Date'].dt.strftime('%B')

        # Add debug info about extracted years before filtering
        print(f"Years in data before filtering: {sales_data['Year'].unique()}")

        # Count records by year
        year_counts = sales_data['Year'].value_counts().sort_index()
        print(f"Records per year: {year_counts.to_dict()}")

        progress_bar.progress(80)

        # Map columns to expected format for the dashboard
        sales_data['SALON NAMES'] = sales_data['Center Name']
        sales_data['BRAND'] = sales_data['Business Unit'].fillna('Other')

        # Rename columns to match the previous format
        sales_data = sales_data.rename(columns={
            'Sales Collected (Exc.Tax)': 'sales_collected_exc_tax',
            'Tax Collected': 'tax_collected',
            'Sales Collected (Inc.Tax)': 'sales_collected_inc_tax',
            'Redeemed': 'redeemed',
            'Collected to Date': 'collected_to_date',
            'Collected': 'collected',
            'Sale Date': 'sale_date',
            'Invoice No': 'invoice_no',
            'Center Name': 'center_name',
            'Item Name': 'item_name',
            'Item Type': 'item_type',
            'Item Category': 'item_category',
            'Item Subcategory': 'item_subcategory',
            'Business Unit': 'business_unit'
        })

        # Group by Year, Month, SALON NAMES, BRAND to calculate metrics
        # Using sales_collected_inc_tax for all sales calculations
        grouped_sales = sales_data.groupby(['Year', 'Month', 'SALON NAMES', 'BRAND']).agg({
            'sales_collected_inc_tax': 'sum',
            'invoice_no': 'nunique'
        }).reset_index()

        # Rename columns to match expected format
        grouped_sales.rename(columns={
            'sales_collected_inc_tax': 'MTD SALES',
            'invoice_no': 'MTD BILLS'
        }, inplace=True)

        # Calculate Average Bill Value with error handling
        grouped_sales['MTD ABV'] = grouped_sales.apply(
            lambda row: row['MTD SALES'] /
            row['MTD BILLS'] if row['MTD BILLS'] > 0 else 0,
            axis=1
        )

        # Clear memory if optimization is enabled
        if MEMORY_OPTIMIZATION:
            # Force garbage collection
            import gc
            gc.collect()

        progress_bar.progress(100)
        status_text.success(f"Successfully loaded {len(sales_data)} records!")

        # Store last refresh time
        st.session_state.last_refresh_time = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')

        # Return the transformed data
        return grouped_sales, sales_data
    except Exception as e:
        st.error(f"Error loading data from S3: {e}")
        return pd.DataFrame(), pd.DataFrame()

    # Load processed service data is no longer needed since we're using the raw data directly
    # service_data = load_processed_service_data()
    # return sales_data, service_data


# Only load data if not already loaded in this session
if not st.session_state.data_loaded:
    with st.spinner("Loading data..."):
        grouped_sales, raw_sales_data = load_data()

        if not grouped_sales.empty and not raw_sales_data.empty:
            # Store in session state
            st.session_state.grouped_sales = grouped_sales
            st.session_state.raw_sales_data = raw_sales_data
            st.session_state.data_loaded = True
else:
    # Use data from session state
    grouped_sales = st.session_state.grouped_sales
    raw_sales_data = st.session_state.raw_sales_data

# Add debug info to check available years
if st.session_state.data_loaded:
    st.sidebar.subheader("Debug Info")

    # Count records by year
    if 'Year' in raw_sales_data.columns:
        year_counts = raw_sales_data['Year'].value_counts().sort_index()
        available_years = sorted(raw_sales_data['Year'].unique())

        st.sidebar.write(f"Available Years in Raw Data: {available_years}")
        st.sidebar.write(f"Records per year: {year_counts.to_dict()}")
    else:
        st.sidebar.warning("No 'Year' column found in raw data!")

    available_years_grouped = sorted(
        grouped_sales['Year'].unique()) if 'Year' in grouped_sales.columns else []
    st.sidebar.write(
        f"Available Years in Grouped Data: {available_years_grouped}")

    # Show earliest and latest dates to debug
    if 'sale_date' in raw_sales_data.columns:
        min_date = raw_sales_data['sale_date'].min()
        max_date = raw_sales_data['sale_date'].max()
        st.sidebar.write(f"Date Range: {min_date} to {max_date}")

    # Add total record count
    st.sidebar.write(f"Total Records: {len(raw_sales_data)}")

# Check if data was successfully loaded
has_data = not grouped_sales.empty if st.session_state.data_loaded else False
has_raw_data = not raw_sales_data.empty if st.session_state.data_loaded else False

# Set service_data to raw_sales_data for service analysis tab
service_data = raw_sales_data.copy() if has_raw_data else pd.DataFrame()
has_service_data = not service_data.empty

# Main dashboard tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["MTD Sales Overview", "Outlet Comparison", "Service & Product Analysis", "Growth Analysis", "Holidays Analysis"])

with tab1:
    st.header("Monthly Sales Overview")

    # Filter controls
    col1, col2, col3 = st.columns(3)

    with col1:
        years = sorted(grouped_sales['Year'].unique())
        # If only one year is available, show a radio button instead of dropdown
        if len(years) == 1:
            st.write("Select Year")
            selected_year = years[0]  # Just use the only available year
            st.info(f"Only data for year {selected_year} is available")
        else:
            selected_year = st.selectbox("Select Year", years)

    with col2:
        brands = sorted(grouped_sales['BRAND'].unique())
        selected_brand = st.selectbox("Select Brand", ["All"] + list(brands))

    with col3:
        months = sorted(grouped_sales['Month'].unique())
        selected_month = st.selectbox("Select Month", ["All"] + list(months))

    # Filter data based on selections
    filtered_data = grouped_sales.copy()

    if selected_year != "All":
        filtered_data = filtered_data[filtered_data['Year'] == selected_year]

    if selected_brand != "All":
        filtered_data = filtered_data[filtered_data['BRAND'] == selected_brand]

    if selected_month != "All":
        filtered_data = filtered_data[filtered_data['Month'] == selected_month]

    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_sales = filtered_data['MTD SALES'].sum()
        st.metric("Total Sales", format_indian_money(total_sales))

    with col2:
        total_bills = filtered_data['MTD BILLS'].sum()
        st.metric("Total Bills", f"{int(total_bills)}")

    with col3:
        avg_bill_value = total_sales / total_bills if total_bills > 0 else 0
        st.metric("Average Bill Value", format_indian_money(avg_bill_value))

    with col4:
        total_outlets = filtered_data['SALON NAMES'].nunique()
        st.metric("Total Outlets", f"{total_outlets}")

    # MTD Sales by Outlet
    st.subheader("Sales by Outlet")

    # Group by salon names and calculate totals
    salon_sales = filtered_data.groupby(
        'SALON NAMES')['MTD SALES'].sum().reset_index()
    salon_sales = salon_sales.sort_values('MTD SALES', ascending=False)

    fig = px.bar(
        salon_sales,
        x='SALON NAMES',
        y='MTD SALES',
        title="MTD Sales by Outlet",
        labels={'MTD SALES': 'Sales', 'SALON NAMES': 'Outlet'},
        color='MTD SALES',
        color_continuous_scale='Viridis'
    )

    fig.update_traces(
        text=salon_sales['MTD SALES'].apply(format_indian_money),
        textposition='outside',
        hovertemplate='%{text}<extra></extra>'
    )
    fig.update_layout(
        xaxis={'categoryorder': 'total descending'},
        yaxis_title='Sales'
    )
    st.plotly_chart(fig, use_container_width=True)

    # Sales Trend Over Months
    if selected_month == "All":
        st.subheader("Monthly Sales Trend")

        monthly_sales = filtered_data.groupby(['Month', 'Year'])[
            'MTD SALES'].sum().reset_index()

        # Create a custom sort order for months
        month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        monthly_sales['Month_Sorted'] = pd.Categorical(
            monthly_sales['Month'], categories=month_order, ordered=True)
        monthly_sales = monthly_sales.sort_values('Month_Sorted')

        fig = px.line(
            monthly_sales,
            x='Month',
            y='MTD SALES',
            color='Year',
            title="Monthly Sales Trend",
            labels={'MTD SALES': 'Sales', 'Month': 'Month'},
            markers=True
        )
        fig.update_traces(
            hovertemplate='%{text}<extra></extra>',
            text=monthly_sales['MTD SALES'].apply(format_indian_money)
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Outlet Comparison")

    # Select specific outlet to compare
    outlet_list = sorted(grouped_sales['SALON NAMES'].unique())
    selected_outlet = st.selectbox(
        "Select Outlet for Detailed Analysis", outlet_list)

    # Filter data for the selected outlet
    outlet_data = grouped_sales[grouped_sales['SALON NAMES']
                                == selected_outlet]

    # Group data by year and month
    outlet_yearly = outlet_data.groupby(['Year', 'Month'])[
        'MTD SALES'].sum().reset_index()

    # Create a custom sort order for months
    month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']

    # Create the Month_Sorted column and sort
    outlet_yearly['Month_Sorted'] = pd.Categorical(
        outlet_yearly['Month'], categories=month_order, ordered=True)
    outlet_yearly = outlet_yearly.sort_values(['Year', 'Month_Sorted'])

    # Display yearly comparison chart
    st.subheader(f"{selected_outlet} - Yearly Comparison")

    fig = px.bar(
        outlet_yearly,
        x='Month',
        y='MTD SALES',
        color='Year',
        barmode='group',
        title=f"Monthly Sales for {selected_outlet} by Year",
        labels={'MTD SALES': 'Sales', 'Month': 'Month', 'Year': 'Year'}
    )
    fig.update_traces(
        hovertemplate='%{text}<extra></extra>',
        text=outlet_yearly['MTD SALES'].apply(format_indian_money)
    )
    st.plotly_chart(fig, use_container_width=True)

    # Calculate year-over-year growth
    if len(outlet_yearly['Year'].unique()) > 1:
        st.subheader("Year-over-Year Growth")

        try:
            # Pivot data for easier comparison
            pivot_data = outlet_yearly.pivot_table(
                index='Month_Sorted',
                columns='Year',
                values='MTD SALES',
                observed=True
            ).reset_index()

            # Get years from the pivot table columns
            years = [col for col in pivot_data.columns if col != 'Month_Sorted']

            if len(years) > 1:
                # Calculate YoY growth percentages
                for i in range(1, len(years)):
                    current_year = years[i]
                    prev_year = years[i-1]
                    colname = f"Growth {prev_year} to {current_year}"
                    pivot_data[colname] = (
                        (pivot_data[current_year] / pivot_data[prev_year]) - 1) * 100
                    # Format the growth percentage with % symbol
                    pivot_data[colname] = pivot_data[colname].apply(
                        lambda x: f"{x:.2f}%")

                # Display the growth table
                pivot_data = pivot_data.rename(
                    columns={'Month_Sorted': 'Month'})
                pivot_data['Month'] = pivot_data['Month'].astype(str)

                # Only show growth columns
                growth_cols = [
                    col for col in pivot_data.columns if 'Growth' in str(col)]

                if growth_cols and not pivot_data.empty:
                    # Get the latest year's data
                    latest_year = years[-1]

                    # Calculate projected values (110% of latest year)
                    pivot_data['Projected (10% Growth)'] = pivot_data[latest_year] * 1.10
                    # Format the projected values with currency symbol and Indian comma format
                    pivot_data['Projected (10% Growth)'] = pivot_data['Projected (10% Growth)'].apply(
                        lambda x: format_indian_money(x)
                    )

                    # Format the year columns with Indian comma format
                    for year in years:
                        pivot_data[year] = pivot_data[year].apply(
                            lambda x: format_indian_money(x))

                    # Update display columns to include projected growth
                    display_cols = ['Month'] + years + \
                        growth_cols + ['Projected (10% Growth)']

                    # Display using st.dataframe
                    st.dataframe(pivot_data[display_cols],
                                 use_container_width=True)
                else:
                    st.info(
                        f"Not enough data to compare growth for {selected_outlet} across years.")
            else:
                st.info(
                    f"Only one year of data available for {selected_outlet}. Need at least two years to calculate growth.")
        except Exception as e:
            st.error(f"Could not calculate growth data: {e}")
            st.info(
                f"Please ensure {selected_outlet} has data for multiple years and months.")

    # Daily Sales Analysis
    if 'DAY SALES' in grouped_sales.columns:
        st.subheader("Daily Sales Analysis")

        # Display day-wise sales if available
        outlet_daily = grouped_sales[
            (grouped_sales['SALON NAMES'] == selected_outlet) &
            # Changed from notna to ~pd.isna for clarity
            (~pd.isna(grouped_sales['DAY SALES'])) &
            # Additional check for empty strings
            (grouped_sales['DAY SALES'] != '') &
            # Additional check for zero values
            (grouped_sales['DAY SALES'] != 0)
        ]

        if not outlet_daily.empty:
            # Group by day and calculate averages
            try:
                daily_avg = outlet_daily.groupby(['Year', 'Month', 'DAY SALES'])[
                    'MTD SALES'].mean().reset_index()

                fig = px.line(
                    daily_avg,
                    x='DAY SALES',
                    y='MTD SALES',
                    color='Year',
                    line_group='Month',
                    title=f"Daily Sales for {selected_outlet}",
                    labels={'MTD SALES': 'Sales (₹)', 'DAY SALES': 'Day'}
                )
                fig.update_traces(
                    hovertemplate='%{text}<extra></extra>',
                    text=daily_avg['MTD SALES'].apply(format_indian_money)
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Error processing daily sales data: {e}")
                st.info(
                    "Daily sales data format may be incorrect. Check the 'DAY SALES' column.")
        else:
            st.info(
                f"No daily sales data available for {selected_outlet}. The 'DAY SALES' column is empty or not properly formatted.")

with tab3:
    st.header("Service & Product Analysis")

    if has_raw_data:
        # Advanced filtering options
        st.subheader("Filter Service Data")

        with st.expander("Advanced Filters", expanded=False):
            filter_cols = st.columns(3)

            with filter_cols[0]:
                service_years = sorted(raw_sales_data['Year'].unique())
                # If only one year is available, show a simple message instead of dropdown
                if len(service_years) == 1:
                    st.write("Select Year")
                    # Use the only available year
                    selected_service_year = service_years[0]
                    st.info(
                        f"Only data for year {selected_service_year} is available")
                else:
                    year_options = ["All Years"] + service_years
                selected_service_year = st.selectbox(
                    "Select Year", year_options, key="service_year_select")

                center_names = sorted(raw_sales_data['center_name'].unique())
                selected_center = st.selectbox(
                    "Select Center", ["All"] + list(center_names), key="service_center_select")

            with filter_cols[1]:
                item_types = ["All"] + \
                    sorted(raw_sales_data['item_type'].unique())
                selected_item_type = st.selectbox(
                    "Select Item Type", item_types, key="item_type_select")

                if 'item_category' in raw_sales_data.columns:
                    item_categories = [
                        "All"] + sorted(raw_sales_data['item_category'].dropna().unique())
                    selected_item_category = st.selectbox(
                        "Select Item Category", item_categories, key="item_category_select")
                else:
                    selected_item_category = "All"

            with filter_cols[2]:
                if 'business_unit' in raw_sales_data.columns:
                    business_units = [
                        "All"] + sorted(raw_sales_data['business_unit'].dropna().unique())
                    selected_business_unit = st.selectbox(
                        "Select Business Unit", business_units, key="business_unit_select")
                else:
                    selected_business_unit = "All"

                if 'item_subcategory' in raw_sales_data.columns:
                    item_subcategories = [
                        "All"] + sorted(raw_sales_data['item_subcategory'].dropna().unique())
                    selected_item_subcategory = st.selectbox(
                        "Select Item Subcategory", item_subcategories, key="item_subcategory_select")
                else:
                    selected_item_subcategory = "All"

        # Filter raw_sales_data
        filtered_service_data = raw_sales_data.copy()
        filtered_service_data = filtered_service_data[filtered_service_data['Year']
                                                      == selected_service_year]

        if selected_center != "All":
            filtered_service_data = filtered_service_data[
                filtered_service_data['center_name'] == selected_center]

        if selected_item_type != "All":
            filtered_service_data = filtered_service_data[filtered_service_data['item_type']
                                                          == selected_item_type]

        if selected_item_category != "All" and 'item_category' in filtered_service_data.columns:
            filtered_service_data = filtered_service_data[
                filtered_service_data['item_category'] == selected_item_category]

        if selected_business_unit != "All" and 'business_unit' in filtered_service_data.columns:
            filtered_service_data = filtered_service_data[
                filtered_service_data['business_unit'] == selected_business_unit]

        if selected_item_subcategory != "All" and 'item_subcategory' in filtered_service_data.columns:
            filtered_service_data = filtered_service_data[
                filtered_service_data['item_subcategory'] == selected_item_subcategory]

        # Service Categories Analysis
        st.subheader("Service Categories Breakdown")

        # Filter data based on selected year or use all years
        if selected_service_year == "All Years":
            breakdown_data = raw_sales_data.copy()  # Use all data
            year_title = "All Years"
        else:
            breakdown_data = raw_sales_data[raw_sales_data['Year']
                                            == selected_service_year].copy()
            year_title = selected_service_year

        # Apply other filters except year
        if selected_center != "All":
            breakdown_data = breakdown_data[
                breakdown_data['center_name'] == selected_center]

        if selected_item_type != "All":
            breakdown_data = breakdown_data[breakdown_data['item_type']
                                            == selected_item_type]

        if selected_item_category != "All" and 'item_category' in breakdown_data.columns:
            breakdown_data = breakdown_data[
                breakdown_data['item_category'] == selected_item_category]

        if selected_business_unit != "All" and 'business_unit' in breakdown_data.columns:
            breakdown_data = breakdown_data[
                breakdown_data['business_unit'] == selected_business_unit]

        if selected_item_subcategory != "All" and 'item_subcategory' in breakdown_data.columns:
            breakdown_data = breakdown_data[
                breakdown_data['item_subcategory'] == selected_item_subcategory]

        # Create two columns for Item Type and Item Category charts
        col1, col2 = st.columns(2)

        with col1:
            if 'item_type' in breakdown_data.columns:
                # Calculate metrics by Item Type
                item_type_sales = breakdown_data.groupby(
                    'item_type')['sales_collected_inc_tax'].sum().reset_index()
                item_type_sales = item_type_sales.sort_values(
                    'sales_collected_inc_tax', ascending=False)

                # Format values for display
                item_type_sales['formatted_sales'] = item_type_sales['sales_collected_inc_tax'].apply(
                    lambda x: format_indian_money(x).replace('₹', '')
                )

                # Create Item Type visualization
                fig = px.pie(
                    item_type_sales,
                    values='sales_collected_inc_tax',
                    names='item_type',
                    title=f"Sales Distribution by Item Type ({year_title})",
                    labels={'sales_collected_inc_tax': 'Sales'},
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Bold
                )

                # Add custom text and hover
                fig.update_traces(
                    texttemplate='%{label}<br>₹%{text}',
                    text=item_type_sales['formatted_sales'],
                    hovertemplate='₹%{text}<extra></extra>'
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Item Type data is not available.")

        with col2:
            # Group by Item Category for visualization
            if 'item_category' in breakdown_data.columns:
                item_category_sales = breakdown_data.groupby(
                    'item_category')['sales_collected_inc_tax'].sum().reset_index()
                item_category_sales = item_category_sales.sort_values(
                    'sales_collected_inc_tax', ascending=False)

                # Format values for display
                item_category_sales['formatted_sales'] = item_category_sales['sales_collected_inc_tax'].apply(
                    lambda x: format_indian_money(x).replace('₹', '')
                )

                fig = px.pie(
                    item_category_sales,
                    values='sales_collected_inc_tax',
                    names='item_category',
                    title=f"Sales Distribution by Item Category ({year_title})",
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    hole=0.4
                )

                # Add custom text and hover
                fig.update_traces(
                    texttemplate='%{label}<br>₹%{text}',
                    text=item_category_sales['formatted_sales'],
                    hovertemplate='₹%{text}<extra></extra>'
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Item Category data is not available.")

        # Hair, Skin, Spa and Products Breakdown section
        st.subheader("Hair, Skin, Spa and Products Breakdown")

        # Get business unit data
        if 'business_unit' in breakdown_data.columns:
            # Group by Business Unit for business unit chart
            business_unit_sales = breakdown_data.groupby(
                'business_unit')['sales_collected_inc_tax'].sum().reset_index()
            business_unit_sales = business_unit_sales.sort_values(
                'sales_collected_inc_tax', ascending=False)

            # Create formatted values for display
            business_unit_sales['formatted_sales'] = business_unit_sales['sales_collected_inc_tax'].apply(
                lambda x: format_indian_money(x).replace('₹', '')
            )

            # Create two columns for the charts
            bu_col1, bu_col2 = st.columns(2)

            with bu_col1:
                # Create Business Unit pie chart
                fig_bu = px.pie(
                    business_unit_sales,
                    values='sales_collected_inc_tax',
                    names='business_unit',
                    title=f"Sales by Business Unit ({year_title})",
                    color_discrete_sequence=px.colors.qualitative.Bold,
                    hole=0.4
                )

                # Add custom text and hover
                fig_bu.update_traces(
                    texttemplate='%{label}<br>₹%{text}',
                    text=business_unit_sales['formatted_sales'],
                    hovertemplate='₹%{text}<extra></extra>'
                )

                # Add total sales in center
                total_sales = business_unit_sales['sales_collected_inc_tax'].sum(
                )
                fig_bu.add_annotation(
                    text=f"Total<br>{format_indian_money(total_sales)}",
                    x=0.5, y=0.5,
                    font_size=14,
                    showarrow=False
                )

                # Improve layout
                fig_bu.update_layout(
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                    margin=dict(t=50, b=100, l=20, r=20)
                )

                st.plotly_chart(fig_bu, use_container_width=True)

            with bu_col2:
                # Create treemap view
                if 'item_category' in breakdown_data.columns:
                    # Create data for treemap
                    hierarchy_data = breakdown_data.groupby(['business_unit', 'item_category'])[
                        'sales_collected_inc_tax'].sum().reset_index()

                    # Remove any zero or negative values that would cause normalization errors
                    hierarchy_data = hierarchy_data[hierarchy_data['sales_collected_inc_tax'] > 0]

                    # Check if we have data after filtering
                    if not hierarchy_data.empty:
                        # Format values for display
                        hierarchy_data['formatted_sales'] = hierarchy_data['sales_collected_inc_tax'].apply(
                            lambda x: format_indian_money(x).replace('₹', '')
                        )

                        # Create treemap
                        fig_tree = px.treemap(
                            hierarchy_data,
                            path=['business_unit', 'item_category'],
                            values='sales_collected_inc_tax',
                            title=f"Hierarchical View of Sales ({year_title})",
                            color='sales_collected_inc_tax',
                            color_continuous_scale='Viridis',
                            custom_data=['formatted_sales']
                        )

                        # Format the labels to show both name and sales amount
                        fig_tree.update_traces(
                            texttemplate='%{label}<br>₹%{customdata[0]}',
                            hovertemplate='%{label}<br>Total: ₹%{customdata[0]}<extra></extra>'
                        )

                        st.plotly_chart(fig_tree, use_container_width=True)
                    else:
                        st.info(
                            "No non-zero data available for hierarchical view.")
                else:
                    st.info(
                        "Item Category data is not available for hierarchical view.")

            # Create bar chart for top categories if item_category is available
            if 'item_category' in breakdown_data.columns:
                # Get top 15 categories by sales
                top_categories = breakdown_data.groupby(['item_category', 'business_unit'])[
                    'sales_collected_inc_tax'].sum().reset_index()
                top_categories = top_categories.sort_values(
                    'sales_collected_inc_tax', ascending=False).head(15)

                # Format values for display
                top_categories['formatted_sales'] = top_categories['sales_collected_inc_tax'].apply(
                    lambda x: format_indian_money(x).replace('₹', '')
                )

                # Create bar chart
                fig_cat = px.bar(
                    top_categories,
                    x='item_category',
                    y='sales_collected_inc_tax',
                    color='business_unit',
                    title=f"Top 15 Service/Product Categories ({year_title})",
                    labels={
                        'sales_collected_inc_tax': 'Sales',
                        'item_category': 'Category',
                        'business_unit': 'Business Unit'
                    },
                    text='formatted_sales'
                )

                # Format the bar chart
                fig_cat.update_traces(
                    texttemplate='₹%{text}',
                    textposition='outside',
                    hovertemplate='₹%{text}<extra></extra>'
                )

                fig_cat.update_layout(
                    xaxis={'categoryorder': 'total descending',
                           'title': 'Category'},
                    yaxis_title='Sales',
                    legend_title='Business Unit'
                )

                st.plotly_chart(fig_cat, use_container_width=True)

                # Add pivot table with top categories by business unit
                st.subheader("Top Categories by Business Unit")

                try:
                    # Ensure invoice_no is numeric and handles string values
                    if 'invoice_no' in breakdown_data.columns:
                        # Convert invoice_no to string first to handle potential mixed types
                        breakdown_data['invoice_no_clean'] = pd.to_numeric(
                            pd.Series([str(x).split('II')[0]
                                      for x in breakdown_data['invoice_no']]),
                            errors='coerce'
                        )
                    else:
                        # Use a dummy column if invoice_no doesn't exist
                        breakdown_data['invoice_no_clean'] = 1

                    # Create pivot table with the clean invoice number
                    pivot = pd.pivot_table(
                        breakdown_data,
                        values=['sales_collected_inc_tax', 'invoice_no_clean'],
                        index='item_category',
                        columns='business_unit',
                        aggfunc='sum',
                        fill_value=0,
                        observed=True
                    )

                    # Format for display - flatten columns and format values
                    pivot_flat = pivot.reset_index()
                    formatted_pivot = pivot_flat.copy()

                    # Format the sales columns with ₹ symbol and Indian comma format
                    for col in formatted_pivot.columns:
                        if isinstance(col, tuple) and col[0] == 'sales_collected_inc_tax':
                            formatted_pivot[col] = formatted_pivot[col].apply(
                                lambda x: format_indian_money(
                                    x) if x > 0 else ""
                            )

                    st.dataframe(formatted_pivot, use_container_width=True)
                except Exception as e:
                    st.error(f"Error creating pivot table: {e}")
                    st.info(
                        "This may be due to mixed data types in the invoice_no column. Showing basic category summary instead.")

                    # Fallback to a simple summary if pivot fails
                    if 'item_category' in breakdown_data.columns:
                        simple_summary = breakdown_data.groupby(
                            'item_category')['sales_collected_inc_tax'].sum().reset_index()
                        simple_summary = simple_summary.sort_values(
                            'sales_collected_inc_tax', ascending=False)
                        simple_summary['sales_collected_inc_tax'] = simple_summary['sales_collected_inc_tax'].apply(
                            format_indian_money)
                        simple_summary.columns = [
                            'Category', 'Sales Value', 'Sales (₹)']
                        st.dataframe(simple_summary, use_container_width=True)
            else:
                st.info("Business unit data is not available.")

            # Continue with existing code for Advanced Service Hierarchy Visualization...

with tab4:
    st.header("Growth Analysis")

    # Compare centers across years if multiple years available
    if len(service_years) > 1:
        st.subheader("Center Performance Across Years")

        # Group by center and year
        yearly_center_sales = raw_sales_data.groupby(['center_name', 'Year'])[
            'sales_collected_inc_tax'].sum().reset_index()

        # Create a comparison visualization
        fig = px.bar(
            yearly_center_sales,
            x='center_name',
            y='sales_collected_inc_tax',
            color='Year',
            barmode='group',
            title="Center Sales by Year",
            labels={'sales_collected_inc_tax': 'Sales',
                    'center_name': 'Center', 'Year': 'Year'}
        )
        fig.update_traces(
            hovertemplate='₹%{y:,.0f}<extra></extra>'
        )
        st.plotly_chart(fig, use_container_width=True)

        # Calculate year-over-year growth for centers
        st.subheader("Center Growth Analysis")

        # Create a pivot table for easier comparison
        center_pivot = yearly_center_sales.pivot_table(
            index='center_name',
            columns='Year',
            values='sales_collected_inc_tax',
            observed=True
        ).reset_index()

        # Calculate growth percentages
        years = sorted(yearly_center_sales['Year'].unique())
        for i in range(1, len(years)):
            prev_year = years[i-1]
            curr_year = years[i]
            growth_col = f'Growth {prev_year}-{curr_year}'
            center_pivot[growth_col] = ((center_pivot[curr_year] /
                                        center_pivot[prev_year] - 1) * 100).round(2)
            center_pivot[growth_col] = center_pivot[growth_col].apply(
                lambda x: f"{x}%")

        # Format sales columns with Indian currency format
        for year in years:
            center_pivot[year] = center_pivot[year].apply(format_indian_money)

        st.dataframe(center_pivot, use_container_width=True)

        # Add projected growth analysis
        st.subheader("Projected Growth Analysis")
        latest_year = years[-1]
        center_pivot['Projected (10% Growth)'] = (yearly_center_sales[yearly_center_sales['Year'] == latest_year]
                                                  ['sales_collected_inc_tax'] * 1.1)
        center_pivot['Projected (10% Growth)'] = center_pivot['Projected (10% Growth)'].apply(
            format_indian_money)
        st.dataframe(center_pivot, use_container_width=True)
    else:
        st.info(
            "Multiple years of data required for growth analysis. Currently only one year is available.")

    # T Nagar Specific Analysis (if T NAGAR exists in the data)
    if 'T NAGAR' in grouped_sales['SALON NAMES'].unique():
        st.header("T NAGAR Outlet Analysis")

        # Filter data for T NAGAR
        t_nagar_data = grouped_sales[grouped_sales['SALON NAMES'] == 'T NAGAR']

        if not t_nagar_data.empty:
            t_nagar_years = sorted(t_nagar_data['Year'].unique())

            # Display T NAGAR yearly comparison
            st.subheader("T NAGAR - Yearly Sales Comparison")

            fig = px.bar(
                t_nagar_data,
                x='Month',
                y='MTD SALES',
                color='Year',
                barmode='stack',
                title="T NAGAR Monthly Sales by Year",
                labels={'MTD SALES': 'Sales (₹)',
                        'Month': 'Month', 'Year': 'Year'}
            )
            fig.update_traces(
                hovertemplate='%{text}<extra></extra>',
                text=t_nagar_data['MTD SALES'].apply(format_indian_money)
            )
            st.plotly_chart(fig, use_container_width=True)

            # Display growth metrics if multiple years
            if len(t_nagar_years) > 1:
                # Calculate year-over-year growth
                t_nagar_yearly = t_nagar_data.groupby(
                    'Year')['MTD SALES'].sum().reset_index()

                # Calculate growth percentages
                t_nagar_growth = []
                for i in range(1, len(t_nagar_yearly)):
                    current_year = t_nagar_yearly.iloc[i]['Year']
                    prev_year = t_nagar_yearly.iloc[i-1]['Year']
                    current_sales = t_nagar_yearly.iloc[i]['MTD SALES']
                    prev_sales = t_nagar_yearly.iloc[i-1]['MTD SALES']
                    growth_pct = ((current_sales / prev_sales) - 1) * 100
                    t_nagar_growth.append({
                        'Year Comparison': f"{prev_year} to {current_year}",
                        'Growth (%)': f"{growth_pct:.2f}%"
                    })

                # Display growth table
                st.dataframe(pd.DataFrame(t_nagar_growth),
                             use_container_width=True)
        else:
            st.info("No monthly data available for T NAGAR outlet.")
    else:
        st.info("T NAGAR outlet not found in the data.")

with tab5:
    st.header("Holidays Analysis")

    # Load leaves data
    try:
        leaves_data_path = "dataset/2024_2025_Leaves.csv"
        if os.path.exists(leaves_data_path):
            leaves_data = pd.read_csv(leaves_data_path)
            leaves_data['Date'] = pd.to_datetime(
                leaves_data['Date'], errors='coerce')
            leaves_data = leaves_data.dropna(subset=['Date'])
            has_leaves_data = True

            # Extract month and day from each holiday/festival date
            leaves_data['month'] = leaves_data['Date'].dt.month
            leaves_data['day'] = leaves_data['Date'].dt.day

            # Generate multi-year festival data
            all_years_data = []

            # Get all available years from raw data
            available_years_in_data = sorted(
                raw_sales_data['sale_date'].dt.year.unique())

            # For each festival in the leaves data
            for _, festival in leaves_data.iterrows():
                month = festival['month']
                day = festival['day']
                festival_name = festival['Festivals']

                # For each available year in raw data
                for year in available_years_in_data:
                    try:
                        # Create the date for this festival in this year
                        festival_date = pd.Timestamp(
                            year=year, month=month, day=day)

                        # Get sales data for this specific date
                        date_sales = raw_sales_data[raw_sales_data['sale_date'].dt.date == festival_date.date(
                        )]

                        if not date_sales.empty:
                            # Calculate total sales for this date
                            total_sales = date_sales['sales_collected_inc_tax'].sum(
                            )

                            # Add to our multi-year dataset
                            all_years_data.append({
                                'Months': festival['Months'],
                                'Date': festival_date,
                                'Festivals': festival_name,
                                'MTD_Sale': total_sales,
                                'Year': year
                            })

                            # Add center-specific data
                            for center in date_sales['center_name'].unique():
                                center_sales = date_sales[date_sales['center_name']
                                                          == center]['sales_collected_inc_tax'].sum()
                                all_years_data.append({
                                    'Months': festival['Months'],
                                    'Date': festival_date,
                                    'Festivals': festival_name,
                                    'MTD_Sale': center_sales,
                                    'Year': year,
                                    'CenterName': center
                                })
                    except Exception as e:
                        print(
                            f"Error processing {festival_name} for {year}: {e}")
                        continue

            # Create a new DataFrame with multi-year data
            if all_years_data:
                multi_year_leaves_data = pd.DataFrame(all_years_data)
                # Use this new DataFrame instead of the original leaves_data
                leaves_data = multi_year_leaves_data
                st.success(
                    f"Successfully generated holiday data for years: {sorted(leaves_data['Year'].unique())}")

        else:
            st.info(f"Leaves data file not found at {leaves_data_path}")
            has_leaves_data = False
    except Exception as e:
        st.warning(f"Could not load leaves data: {e}")
        has_leaves_data = False

    if has_leaves_data and has_raw_data:
        # Create filters
        st.subheader("Holiday Analysis Filters")
        filter_cols = st.columns([2, 2, 2])

        with filter_cols[0]:
            # Get unique festivals
            festivals = sorted(leaves_data['Festivals'].unique())
            selected_festival = st.selectbox(
                "Select Holiday/Festival",
                festivals,
                key="festival_select"
            )

        with filter_cols[1]:
            # Get available years from the multi-year leaves data
            available_years = sorted(leaves_data['Year'].unique())
            selected_years = st.multiselect(
                "Select Years to Compare",
                available_years,
                default=available_years,
                key="years_multiselect"
            )

        with filter_cols[2]:
            # Filter by center name if available
            if 'CenterName' in leaves_data.columns:
                center_names = sorted(
                    leaves_data['CenterName'].dropna().unique())
                selected_center = st.selectbox(
                    "Select Center",
                    ["All Centers"] + list(center_names),
                    key="center_select"
                )
            else:
                selected_center = "All Centers"

        # Create scrollable bar chart for holiday sales
        st.subheader("Holiday Sales Comparison")

        # Filter leaves data for selected years
        filtered_leaves = leaves_data[leaves_data['Year'].isin(selected_years)]

        # Filter by center if a specific center is selected
        if selected_center != "All Centers" and 'CenterName' in filtered_leaves.columns:
            filtered_leaves = filtered_leaves[filtered_leaves['CenterName']
                                              == selected_center]
        elif selected_center != "All Centers":
            # If center column doesn't exist, display message and continue with unfiltered data
            st.info(
                f"Filtering by center '{selected_center}' but center data is not available.")

        # If selecting all centers, only use rows without center information (to avoid double counting)
        if selected_center == "All Centers" and 'CenterName' in filtered_leaves.columns:
            filtered_leaves = filtered_leaves[~filtered_leaves['CenterName'].notna(
            )]

        # Create bar chart
        fig_holidays = px.bar(
            filtered_leaves,
            x='Festivals',
            y='MTD_Sale',
            color='Year',
            title="Sales Performance on Holidays",
            labels={
                'MTD_Sale': 'Sales',
                'Festivals': 'Holiday/Festival'
            },
            barmode='group'
        )

        # Update layout for better readability
        fig_holidays.update_layout(
            xaxis_tickangle=-45,
            xaxis={'categoryorder': 'total descending'},
            height=500,
            margin=dict(b=100)  # Add bottom margin for rotated labels
        )

        # Format hover template
        fig_holidays.update_traces(
            hovertemplate='%{y:,.0f}<extra></extra>'
        )

        st.plotly_chart(fig_holidays, use_container_width=True)

        # Analyze selected festival performance
        if selected_festival:
            st.subheader(f"Detailed Analysis: {selected_festival}")

            # Get the date of the selected festival for each year
            festival_dates = leaves_data[(leaves_data['Festivals'] == selected_festival) &
                                         (leaves_data['Year'].isin(selected_years))]['Date']

            # Create date ranges for analysis (±3 days)
            analysis_data = []

            for festival_date in festival_dates:
                start_date = festival_date - pd.Timedelta(days=3)
                end_date = festival_date + pd.Timedelta(days=2)

                # Filter sales data by center if needed
                sales_data_to_use = raw_sales_data
                if selected_center != "All Centers":
                    sales_data_to_use = raw_sales_data[raw_sales_data['center_name']
                                                       == selected_center]

                # Filter raw sales data for the date range
                date_range_data = sales_data_to_use[
                    (sales_data_to_use['sale_date'] >= start_date) &
                    (sales_data_to_use['sale_date'] <= end_date)
                ]

                if not date_range_data.empty:
                    # Calculate daily totals
                    daily_sales = date_range_data.groupby('sale_date').agg({
                        'sales_collected_inc_tax': 'sum'
                    }).reset_index()

                    # Add relative day column
                    daily_sales['Days from Festival'] = (
                        daily_sales['sale_date'] - festival_date).dt.days
                    daily_sales['Year'] = daily_sales['sale_date'].dt.year
                    daily_sales['Festival'] = selected_festival
                    analysis_data.append(daily_sales)

            if analysis_data:
                # Combine all analysis data
                combined_analysis = pd.concat(analysis_data)

                # Create histogram
                fig_analysis = px.bar(
                    combined_analysis,
                    x='Days from Festival',
                    y='sales_collected_inc_tax',
                    color='Year',
                    title=f"Sales Distribution Around {selected_festival}" + (
                        f" - {selected_center}" if selected_center != "All Centers" else ""),
                    labels={
                        'Days from Festival': 'Days (Negative = Before, Positive = After)',
                        'sales_collected_inc_tax': 'Sales'
                    },
                    barmode='group'
                )

                fig_analysis.update_traces(
                    hovertemplate='₹%{y:,.0f}<extra></extra>'
                )

                st.plotly_chart(fig_analysis, use_container_width=True)

                # Create performance summary table
                st.subheader("Best Performing Holidays (±3 Days Window)")

                # Calculate total sales for each festival window
                festival_performance = []
                for festival in leaves_data['Festivals'].unique():
                    # Get dates for this festival across all selected years
                    festival_dates = leaves_data[(leaves_data['Festivals'] == festival) &
                                                 (leaves_data['Year'].isin(selected_years))]['Date']

                    for festival_date in festival_dates:
                        year = festival_date.year
                        start_date = festival_date - pd.Timedelta(days=3)
                        end_date = festival_date + pd.Timedelta(days=2)

                        # Filter by center if needed
                        if selected_center != "All Centers":
                            window_data = raw_sales_data[
                                (raw_sales_data['center_name'] == selected_center) &
                                (raw_sales_data['sale_date'] >= start_date) &
                                (raw_sales_data['sale_date'] <= end_date)
                            ]
                            center_name = selected_center
                        else:
                            window_data = raw_sales_data[
                                (raw_sales_data['sale_date'] >= start_date) &
                                (raw_sales_data['sale_date'] <= end_date)
                            ]
                            center_name = "All Centers"

                        window_sales = window_data['sales_collected_inc_tax'].sum(
                        )

                        # Only add if there are sales
                        if window_sales > 0:
                            festival_performance.append({
                                'Festival': festival,
                                'Year': year,
                                'Date': festival_date,
                                'Center': center_name,
                                'Total Window Sales': window_sales,
                                'Average Daily Sales': window_sales / 6  # 6 days window
                            })

                # Create DataFrame and sort by total sales
                if festival_performance:
                    performance_df = pd.DataFrame(festival_performance)
                    performance_df = performance_df.sort_values(
                        'Total Window Sales', ascending=False)

                    # Format currency columns
                    performance_df['Total Window Sales'] = performance_df['Total Window Sales'].apply(
                        format_indian_money)
                    performance_df['Average Daily Sales'] = performance_df['Average Daily Sales'].apply(
                        format_indian_money)

                    # Display the table
                    st.dataframe(
                        performance_df,
                        column_config={
                            'Festival': 'Festival/Holiday',
                            'Year': 'Year',
                            'Date': 'Festival Date',
                            'Center': 'Center',
                            'Total Window Sales': 'Total Sales (±3 Days)',
                            'Average Daily Sales': 'Average Daily Sales'
                        },
                        use_container_width=True
                    )

                    # Add service category breakdown for the selected festival
                    st.subheader(
                        f"Service Category Breakdown for {selected_festival}")

                    # Get all sales data for the selected festival within the date window
                    festival_sales_data = []

                    for festival_date in leaves_data[(leaves_data['Festivals'] == selected_festival) &
                                                     (leaves_data['Year'].isin(selected_years))]['Date']:
                        year = festival_date.year
                        start_date = festival_date - pd.Timedelta(days=3)
                        end_date = festival_date + pd.Timedelta(days=2)

                        # Filter by center if needed
                        if selected_center != "All Centers":
                            date_window_data = raw_sales_data[
                                (raw_sales_data['center_name'] == selected_center) &
                                (raw_sales_data['sale_date'] >= start_date) &
                                (raw_sales_data['sale_date'] <= end_date)
                            ]
                        else:
                            date_window_data = raw_sales_data[
                                (raw_sales_data['sale_date'] >= start_date) &
                                (raw_sales_data['sale_date'] <= end_date)
                            ]

                        if not date_window_data.empty:
                            festival_sales_data.append(date_window_data)

                    if festival_sales_data:
                        # Combine all sales data
                        combined_festival_data = pd.concat(festival_sales_data)

                        # Add year column for analysis
                        combined_festival_data['Year'] = combined_festival_data['sale_date'].dt.year

                        # Create tabs for different breakdowns
                        breakdown_tab1, breakdown_tab2, breakdown_tab3 = st.tabs(
                            ["Service Category Analysis",
                                "Business Unit Analysis", "Top Services"]
                        )

                        with breakdown_tab1:
                            # Analyze by item_category
                            if 'item_category' in combined_festival_data.columns:
                                # Group by category and year
                                category_data = combined_festival_data.groupby(
                                    ['item_category', 'Year'])['sales_collected_inc_tax'].sum().reset_index()

                                # Create bar chart
                                fig_category = px.bar(
                                    category_data,
                                    x='item_category',
                                    y='sales_collected_inc_tax',
                                    color='Year',
                                    title=f"Service Categories During {selected_festival}",
                                    labels={
                                        'item_category': 'Service Category',
                                        'sales_collected_inc_tax': 'Sales'
                                    },
                                    barmode='group'
                                )

                                fig_category.update_layout(
                                    xaxis_title='Service Category',
                                    yaxis_title='Sales',
                                    xaxis={'categoryorder': 'total descending'}
                                )

                                fig_category.update_traces(
                                    hovertemplate='₹%{y:,.0f}<extra></extra>'
                                )

                                st.plotly_chart(
                                    fig_category, use_container_width=True)

                                # Create a pie chart showing category distribution
                                category_total = combined_festival_data.groupby(
                                    'item_category')['sales_collected_inc_tax'].sum().reset_index()

                                category_total['formatted_sales'] = category_total['sales_collected_inc_tax'].apply(
                                    lambda x: format_indian_money(
                                        x).replace('₹', '')
                                )

                                fig_pie = px.pie(
                                    category_total,
                                    values='sales_collected_inc_tax',
                                    names='item_category',
                                    title=f"Service Category Distribution for {selected_festival}",
                                    hole=0.4
                                )

                                fig_pie.update_traces(
                                    texttemplate='%{label}<br>₹%{text}',
                                    text=category_total['formatted_sales'],
                                    hovertemplate='%{label}<br>₹%{text}<extra></extra>'
                                )

                                st.plotly_chart(
                                    fig_pie, use_container_width=True)
                            else:
                                st.info(
                                    "No category data available for analysis.")

                        with breakdown_tab2:
                            # Analyze by business_unit
                            if 'business_unit' in combined_festival_data.columns:
                                # Group by business unit and year
                                business_data = combined_festival_data.groupby(
                                    ['business_unit', 'Year'])['sales_collected_inc_tax'].sum().reset_index()

                                # Create bar chart
                                fig_business = px.bar(
                                    business_data,
                                    x='business_unit',
                                    y='sales_collected_inc_tax',
                                    color='Year',
                                    title=f"Business Units During {selected_festival}",
                                    labels={
                                        'business_unit': 'Business Unit',
                                        'sales_collected_inc_tax': 'Sales'
                                    },
                                    barmode='group'
                                )

                                fig_business.update_layout(
                                    xaxis_title='Business Unit',
                                    yaxis_title='Sales',
                                    xaxis={'categoryorder': 'total descending'}
                                )

                                fig_business.update_traces(
                                    hovertemplate='₹%{y:,.0f}<extra></extra>'
                                )

                                st.plotly_chart(
                                    fig_business, use_container_width=True)

                                # Create a comparison of business units by center
                                if selected_center == "All Centers":
                                    # Only show this chart if we're looking at all centers
                                    center_business = combined_festival_data.groupby(
                                        ['center_name', 'business_unit'])['sales_collected_inc_tax'].sum().reset_index()

                                    # Get top 10 centers by sales
                                    top_centers = combined_festival_data.groupby(
                                        'center_name')['sales_collected_inc_tax'].sum().nlargest(10).index.tolist()
                                    center_business = center_business[center_business['center_name'].isin(
                                        top_centers)]

                                    fig_center_biz = px.bar(
                                        center_business,
                                        x='center_name',
                                        y='sales_collected_inc_tax',
                                        color='business_unit',
                                        title=f"Business Unit Distribution by Center During {selected_festival}",
                                        labels={
                                            'center_name': 'Center',
                                            'sales_collected_inc_tax': 'Sales',
                                            'business_unit': 'Business Unit'
                                        }
                                    )

                                    fig_center_biz.update_layout(
                                        xaxis_title='Center',
                                        yaxis_title='Sales',
                                        xaxis={
                                            'categoryorder': 'total descending'}
                                    )

                                    fig_center_biz.update_traces(
                                        hovertemplate='₹%{y:,.0f}<extra></extra>'
                                    )

                                    st.plotly_chart(
                                        fig_center_biz, use_container_width=True)
                            else:
                                st.info(
                                    "No business unit data available for analysis.")

                        with breakdown_tab3:
                            # Show top performing services during the festival
                            if 'item_name' in combined_festival_data.columns:
                                # Group by item name and get top services
                                top_services = combined_festival_data.groupby(
                                    'item_name')['sales_collected_inc_tax'].sum().reset_index()
                                top_services = top_services.sort_values(
                                    'sales_collected_inc_tax', ascending=False).head(15)

                                # Format for display
                                top_services['formatted_sales'] = top_services['sales_collected_inc_tax'].apply(
                                    format_indian_money)

                                # Create bar chart
                                fig_services = px.bar(
                                    top_services,
                                    x='item_name',
                                    y='sales_collected_inc_tax',
                                    title=f"Top 15 Services During {selected_festival}",
                                    labels={
                                        'item_name': 'Service Name',
                                        'sales_collected_inc_tax': 'Sales'
                                    },
                                    text='formatted_sales'
                                )

                                fig_services.update_layout(
                                    xaxis_title='Service',
                                    yaxis_title='Sales',
                                    xaxis={
                                        'categoryorder': 'total descending', 'tickangle': -45}
                                )

                                fig_services.update_traces(
                                    textposition='outside',
                                    hovertemplate='%{x}<br>%{text}<extra></extra>'
                                )

                                st.plotly_chart(
                                    fig_services, use_container_width=True)

                                # Show service counts (popularity) not just revenue
                                service_counts = combined_festival_data.groupby(
                                    'item_name').size().reset_index(name='count')
                                service_counts = service_counts.sort_values(
                                    'count', ascending=False).head(15)

                                fig_counts = px.bar(
                                    service_counts,
                                    x='item_name',
                                    y='count',
                                    title=f"Most Popular Services During {selected_festival} (by Count)",
                                    labels={
                                        'item_name': 'Service Name',
                                        'count': 'Number of Services'
                                    },
                                    text='count'
                                )

                                fig_counts.update_layout(
                                    xaxis_title='Service',
                                    yaxis_title='Count',
                                    xaxis={
                                        'categoryorder': 'total descending', 'tickangle': -45}
                                )

                                fig_counts.update_traces(
                                    textposition='outside',
                                    hovertemplate='%{x}<br>%{y} services<extra></extra>'
                                )

                                st.plotly_chart(
                                    fig_counts, use_container_width=True)

                                # Create a summary table with more details
                                st.subheader("Top Services Summary")

                                # Create a comprehensive summary
                                service_summary = combined_festival_data.groupby(
                                    ['item_name', 'item_category', 'business_unit']
                                ).agg({
                                    'sales_collected_inc_tax': 'sum',
                                    'invoice_no': 'nunique'  # Count unique invoices as a proxy for service count
                                }).reset_index()

                                # Calculate average price
                                service_summary['average_price'] = service_summary['sales_collected_inc_tax'] / \
                                    service_summary['invoice_no']

                                # Sort by revenue
                                service_summary = service_summary.sort_values(
                                    'sales_collected_inc_tax', ascending=False).head(20)

                                # Format for display
                                service_summary['sales_collected_inc_tax'] = service_summary['sales_collected_inc_tax'].apply(
                                    format_indian_money)
                                service_summary['average_price'] = service_summary['average_price'].apply(
                                    format_indian_money)

                                # Rename columns for display
                                service_summary.columns = [
                                    'Service Name', 'Category', 'Business Unit', 'Total Revenue', 'Service Count', 'Average Price']

                                # Display the table
                                st.dataframe(service_summary,
                                             use_container_width=True)
                            else:
                                st.info(
                                    "No detailed service data available for analysis.")

                        # Add daily analysis by invoice count
                        st.subheader(
                            f"Daily Traffic During {selected_festival}")

                        # Group by date and count invoices
                        daily_traffic = combined_festival_data.groupby(
                            pd.Grouper(key='sale_date', freq='D')
                        ).agg({
                            'invoice_no': 'nunique',
                            'sales_collected_inc_tax': 'sum'
                        }).reset_index()

                        # Add relative day column for selected festival
                        for festival_date in leaves_data[(leaves_data['Festivals'] == selected_festival) &
                                                         (leaves_data['Year'].isin(selected_years))]['Date']:
                            matching_rows = daily_traffic[daily_traffic['sale_date'].dt.date == festival_date.date(
                            )]
                            if not matching_rows.empty:
                                # Mark the festival day
                                daily_traffic.loc[matching_rows.index,
                                                  'is_festival'] = True

                        # Create a dual y-axis chart for traffic and revenue
                        fig_traffic = make_subplots(
                            specs=[[{"secondary_y": True}]])

                        # Add invoice count trace
                        fig_traffic.add_trace(
                            go.Bar(
                                x=daily_traffic['sale_date'],
                                y=daily_traffic['invoice_no'],
                                name="Customer Count",
                                marker_color='royalblue'
                            ),
                            secondary_y=False
                        )

                        # Add revenue trace
                        fig_traffic.add_trace(
                            go.Scatter(
                                x=daily_traffic['sale_date'],
                                y=daily_traffic['sales_collected_inc_tax'],
                                name="Revenue",
                                marker_color='firebrick',
                                mode='lines+markers'
                            ),
                            secondary_y=True
                        )

                        # Add vertical lines for festival dates
                        for festival_date in leaves_data[(leaves_data['Festivals'] == selected_festival) &
                                                         (leaves_data['Year'].isin(selected_years))]['Date']:
                            # Use add_shape instead of add_vline for better compatibility
                            fig_traffic.add_shape(
                                type="line",
                                x0=festival_date,
                                y0=0,
                                x1=festival_date,
                                y1=1,
                                line=dict(
                                    color="green",
                                    width=2,
                                    dash="dash",
                                ),
                                xref="x",
                                yref="paper"
                            )

                            # Add annotation separately
                            fig_traffic.add_annotation(
                                x=festival_date,
                                y=1,
                                text="Festival Day",
                                showarrow=False,
                                yshift=10
                            )

                        # Update layout
                        fig_traffic.update_layout(
                            title_text=f"Daily Customer Count and Revenue Around {selected_festival}",
                            xaxis_title="Date",
                            hovermode="x unified"
                        )

                        # Set y-axes titles
                        fig_traffic.update_yaxes(
                            title_text="Customer Count", secondary_y=False)
                        fig_traffic.update_yaxes(
                            title_text="Revenue (₹)", secondary_y=True)

                        st.plotly_chart(fig_traffic, use_container_width=True)
                    else:
                        st.info(
                            "No detailed service analysis available for the selected criteria.")
                else:
                    st.info("No sales data found for the selected criteria.")
            else:
                st.info(
                    f"No sales data found around {selected_festival} for the selected years.")
    else:
        if not has_leaves_data:
            st.info("Holiday/Festival data is required for this analysis.")
        if not has_raw_data:
            st.info("Sales data is required for this analysis.")

# Add footer
st.markdown("---")
st.caption("Executive Dashboard - Created with Streamlit and Plotly")

try:
    pass  # Replace with actual app code
except Exception as e:
    with open("error_log.txt", "w") as f:
        f.write(f"Error: {str(e)}\n")
        f.write(traceback.format_exc())
    st.error(f"App failed to load: {str(e)}")
