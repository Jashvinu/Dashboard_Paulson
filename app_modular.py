import streamlit as st
import pandas as pd
import os
from data_loader import load_all_data
from dashboard_tabs import (
    render_mtd_sales_tab,
    render_outlet_comparison_tab,
    # Uncomment these when implemented
    # render_service_analysis_tab,
    # render_growth_analysis_tab,
    render_holidays_analysis_tab
)

# Set page configuration
st.set_page_config(
    page_title=st.secrets.get("DASHBOARD_TITLE", "Salon Business Dashboard"),
    page_icon="💇",
    layout="wide"
)

# Title and description
st.title(st.secrets.get("DASHBOARD_TITLE", "Executive Business Dashboard"))
st.markdown(st.secrets.get("DASHBOARD_SUBTITLE",
            "Sales and Service Performance Analytics"))

# Initialize session state for data storage
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
    st.session_state.dashboard_data = None
    st.session_state.last_refresh_time = None

# Add sidebar controls
st.sidebar.title("Dashboard Controls")

# Add a more prominent button to clear cache and refresh data
refresh_col1, refresh_col2 = st.sidebar.columns([3, 1])
with refresh_col1:
    if st.button("🔄 Refresh All Data", use_container_width=True):
        # Clear all caches and session state
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state.data_loaded = False
        st.session_state.dashboard_data = None
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

# Load data
if not st.session_state.data_loaded:
    with st.spinner("Loading data..."):
        # Load all data using the centralized data loader
        dashboard_data = load_all_data()

        # Check if data loaded successfully
        if dashboard_data["sales"]["success"]:
            # Store in session state
            st.session_state.dashboard_data = dashboard_data
            st.session_state.data_loaded = True
            st.session_state.last_refresh_time = dashboard_data["timestamp"]
        else:
            st.error(
                f"Error loading data: {dashboard_data['sales'].get('error', 'Unknown error')}")
else:
    # Use data from session state
    dashboard_data = st.session_state.dashboard_data

# Add debug info to check available years
if st.session_state.data_loaded:
    st.sidebar.subheader("Debug Info")

    raw_sales_data = dashboard_data["sales"]["raw_data"]

    # Count records by year
    if 'Year' in raw_sales_data.columns:
        year_counts = raw_sales_data['Year'].value_counts().sort_index()
        available_years = sorted(raw_sales_data['Year'].unique())

        st.sidebar.write(f"Available Years in Raw Data: {available_years}")
        st.sidebar.write(f"Records per year: {year_counts.to_dict()}")
    else:
        st.sidebar.warning("No 'Year' column found in raw data!")

    # Show earliest and latest dates to debug
    if 'sale_date' in raw_sales_data.columns:
        min_date = raw_sales_data['sale_date'].min()
        max_date = raw_sales_data['sale_date'].max()
        st.sidebar.write(f"Date Range: {min_date} to {max_date}")

    # Add total record count
    st.sidebar.write(f"Total Records: {len(raw_sales_data)}")

# Check if data was successfully loaded
has_data = st.session_state.data_loaded

# Main dashboard tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["MTD Sales Overview", "Outlet Comparison",
        "Service & Product Analysis", "Growth Analysis", "Holidays Analysis"]
)

if has_data:
    # Render each tab with the appropriate function
    with tab1:
        render_mtd_sales_tab(dashboard_data)

    with tab2:
        render_outlet_comparison_tab(dashboard_data)

    # Add Service & Product Analysis tab here when implemented
    with tab3:
        st.header("Service & Product Analysis")
        st.info("This tab is under development. Please check back later.")
        # render_service_analysis_tab(dashboard_data)

    # Add Growth Analysis tab here when implemented
    with tab4:
        st.header("Growth Analysis")
        st.info("This tab is under development. Please check back later.")
        # render_growth_analysis_tab(dashboard_data)

    with tab5:
        render_holidays_analysis_tab(dashboard_data)
else:
    # Display loading information if data is not yet loaded
    with tab1:
        st.info(
            "Please wait for data to load or refresh the data using the sidebar button.")

# Add footer
st.markdown("---")
st.caption("Executive Dashboard - Created with Streamlit and Plotly")
