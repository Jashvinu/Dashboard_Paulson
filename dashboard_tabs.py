import streamlit as st
import pandas as pd
import plotly.express as px
from format_utils import format_indian_money, add_month_sorting_column, create_month_order
from visualization import create_bar_chart, create_line_chart, create_pie_chart, create_treemap, display_metric_cards, add_vertical_line


def render_mtd_sales_tab(data):
    """Render the MTD Sales Overview tab"""
    st.header("Monthly Sales Overview")
    grouped_sales = data["sales"]["grouped_data"]

    if grouped_sales.empty:
        st.error("No sales data available. Please refresh the data.")
        return

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
    total_sales = filtered_data['MTD SALES'].sum()
    total_bills = filtered_data['MTD BILLS'].sum()
    avg_bill_value = total_sales / total_bills if total_bills > 0 else 0
    total_outlets = filtered_data['SALON NAMES'].nunique()

    metrics_data = [
        ("Total Sales", format_indian_money(
            total_sales), None, None, "Total sales value"),
        ("Total Bills", f"{int(total_bills)}",
         None, None, "Number of bills generated"),
        ("Average Bill Value", format_indian_money(
            avg_bill_value), None, None, "Average value per bill"),
        ("Total Outlets", f"{total_outlets}",
         None, None, "Number of active outlets")
    ]

    display_metric_cards(metrics_data)

    # MTD Sales by Outlet
    st.subheader("Sales by Outlet")

    # Group by salon names and calculate totals
    salon_sales = filtered_data.groupby(
        'SALON NAMES')['MTD SALES'].sum().reset_index()
    salon_sales = salon_sales.sort_values('MTD SALES', ascending=False)

    # Create bar chart for salon sales
    fig_salon = create_bar_chart(
        salon_sales,
        x='SALON NAMES',
        y='MTD SALES',
        title="MTD Sales by Outlet",
        color='MTD SALES',
        color_continuous_scale='Viridis',
        text_format='money'
    )

    fig_salon.update_layout(
        xaxis={'categoryorder': 'total descending'},
        yaxis_title='Sales'
    )

    st.plotly_chart(fig_salon, use_container_width=True)

    # Sales Trend Over Months
    if selected_month == "All":
        st.subheader("Monthly Sales Trend")

        monthly_sales = filtered_data.groupby(['Month', 'Year'])[
            'MTD SALES'].sum().reset_index()

        # Add month sorting
        monthly_sales = add_month_sorting_column(monthly_sales)
        monthly_sales = monthly_sales.sort_values('Month_Sorted')

        # Create line chart for monthly trend
        fig_monthly = create_line_chart(
            monthly_sales,
            x='Month',
            y='MTD SALES',
            color='Year',
            title="Monthly Sales Trend",
            markers=True,
            text_format='money',
            category_orders={'Month': create_month_order()}
        )

        st.plotly_chart(fig_monthly, use_container_width=True)


def render_outlet_comparison_tab(data):
    """Render the Outlet Comparison tab"""
    st.header("Outlet Comparison")
    grouped_sales = data["sales"]["grouped_data"]

    if grouped_sales.empty:
        st.error("No sales data available. Please refresh the data.")
        return

    # Select specific outlet to compare
    outlet_list = sorted(grouped_sales['SALON NAMES'].unique())
    selected_outlet = st.selectbox(
        "Select Outlet for Detailed Analysis", outlet_list
    )

    # Filter data for the selected outlet
    outlet_data = grouped_sales[grouped_sales['SALON NAMES']
                                == selected_outlet]

    # Group data by year and month
    outlet_yearly = outlet_data.groupby(['Year', 'Month'])[
        'MTD SALES'].sum().reset_index()

    # Add month sorting column
    outlet_yearly = add_month_sorting_column(outlet_yearly)
    outlet_yearly = outlet_yearly.sort_values(['Year', 'Month_Sorted'])

    # Display yearly comparison chart
    st.subheader(f"{selected_outlet} - Yearly Comparison")

    # Create bar chart for outlet comparison
    fig_outlet = create_bar_chart(
        outlet_yearly,
        x='Month',
        y='MTD SALES',
        color='Year',
        title=f"Monthly Sales for {selected_outlet} by Year",
        text_format='money',
        barmode='group',
        category_orders={'Month': create_month_order()}
    )

    st.plotly_chart(fig_outlet, use_container_width=True)

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


def render_holidays_analysis_tab(data):
    """Render the Holidays Analysis tab"""
    st.header("Holidays Analysis")

    raw_sales_data = data["sales"]["raw_data"]
    leaves_data = data["leaves"]["data"] if data["leaves"]["success"] else pd.DataFrame()

    has_raw_data = not raw_sales_data.empty
    has_leaves_data = not leaves_data.empty

    if has_raw_data:
        # Create filters
        st.subheader("Holiday Analysis Filters")
        filter_cols = st.columns([2, 2, 2])

        # Generate holiday data for all available years
        try:
            # Convert all dates to datetime if needed
            raw_sales_data['sale_date'] = pd.to_datetime(
                raw_sales_data['sale_date'])
            available_years = sorted(
                raw_sales_data['sale_date'].dt.year.unique())

            # Create synthetic holidays data from raw_sales_data and leaves_data
            all_holiday_data = []

            # Fall back to original leaves data if needed
            source_data = leaves_data if has_leaves_data else pd.DataFrame()

            if not has_leaves_data:
                # If no leaves data, create a basic holiday structure
                # for major holidays in India
                basic_holidays = [
                    {"month": 1, "day": 1, "festival": "New Year"},
                    {"month": 1, "day": 14, "festival": "Pongal/Makar Sankranti"},
                    {"month": 1, "day": 26, "festival": "Republic Day"},
                    {"month": 8, "day": 15, "festival": "Independence Day"},
                    {"month": 10, "day": 2, "festival": "Gandhi Jayanti"},
                    {"month": 10, "day": 24, "festival": "Diwali"},  # Approximate
                    {"month": 12, "day": 25, "festival": "Christmas"}
                ]

                # Create a basic dataframe for holidays
                temp_data = []
                for holiday in basic_holidays:
                    for year in available_years:
                        try:
                            date = pd.Timestamp(
                                year=year, month=holiday["month"], day=holiday["day"])
                            temp_data.append({
                                "Date": date,
                                "Festivals": holiday["festival"]
                            })
                        except:
                            pass  # Skip invalid dates

                if temp_data:
                    source_data = pd.DataFrame(temp_data)
                    st.info(
                        "Using basic holiday calendar since leaves data is not available.")

            if not source_data.empty:
                # Ensure date column is datetime
                source_data['Date'] = pd.to_datetime(source_data['Date'])

                # Extract month and day for matching across years
                source_data['month'] = source_data['Date'].dt.month
                source_data['day'] = source_data['Date'].dt.day

                # For each holiday in source data
                for _, holiday in source_data.iterrows():
                    month = holiday['month']
                    day = holiday['day']
                    festival = holiday['Festivals']

                    # For each available year in the sales data
                    for year in available_years:
                        try:
                            # Create date for this festival in this year
                            festival_date = pd.Timestamp(
                                year=year, month=month, day=day)

                            # Extract MTD sales directly from the raw sales data
                            date_sales = raw_sales_data[raw_sales_data['sale_date'].dt.date == festival_date.date(
                            )]

                            if not date_sales.empty:
                                total_sales = date_sales['sales_collected_exc_tax'].sum(
                                )

                                # Create a record for this holiday
                                all_holiday_data.append({
                                    'Festivals': festival,
                                    'Date': festival_date,
                                    'Year': year,
                                    'MTD_Sale': total_sales
                                })

                                # Add center-specific data (for dropdown filtering)
                                for center in date_sales['center_name'].unique():
                                    center_sales = date_sales[date_sales['center_name']
                                                              == center]['sales_collected_exc_tax'].sum()
                                    all_holiday_data.append({
                                        'Festivals': festival,
                                        'Date': festival_date,
                                        'Year': year,
                                        'Center': center,
                                        'MTD_Sale': center_sales
                                    })
                        except Exception as e:
                            print(
                                f"Error processing {festival} for {year}: {e}")
                            # Skip invalid dates or errors
                            continue

                # Convert to DataFrame
                holiday_df = pd.DataFrame(all_holiday_data)

                if not holiday_df.empty:
                    # Add information about data source
                    st.success(
                        f"Successfully generated holiday data for years: {sorted(holiday_df['Year'].unique())}")
                else:
                    st.warning(
                        "Could not generate holiday data. Using original data if available.")
                    if has_leaves_data:
                        holiday_df = leaves_data.copy()
                        holiday_df['Year'] = holiday_df['Date'].dt.year
                    else:
                        st.error("No holiday data available for analysis.")
                        return
            else:
                st.error("No source data available to generate holiday analysis.")
                return
        except Exception as e:
            st.error(f"Error generating holiday data: {e}")

            # Fall back to original leaves data if available
            if has_leaves_data:
                holiday_df = leaves_data.copy()
                holiday_df['Year'] = holiday_df['Date'].dt.year
                st.warning(
                    "Using original leaves data due to error generating holiday information.")
            else:
                st.error("No holiday data available for analysis.")
                return

        # Extract unique centers for filtering
        all_centers = sorted(raw_sales_data['center_name'].unique())

        with filter_cols[0]:
            # Get unique festivals
            festivals = sorted(holiday_df['Festivals'].unique())
            selected_festival = st.selectbox(
                "Select Holiday/Festival",
                festivals,
                key="festival_select"
            )

        with filter_cols[1]:
            # Center selection
            selected_center = st.selectbox(
                "Select Center",
                ["All Centers"] + list(all_centers),
                key="holiday_center_select"
            )

        with filter_cols[2]:
            # Convert years to strings for multiselect
            available_years_str = [str(year) for year in available_years]
            selected_years = st.multiselect(
                "Select Years to Compare",
                available_years_str,
                default=available_years_str,
                key="years_multiselect"
            )

        # Create scrollable bar chart for holiday sales
        st.subheader("Holiday Sales Comparison")

        # Filter holiday data for selected years and centers
        filtered_holidays = holiday_df.copy()
        filtered_holidays = filtered_holidays[filtered_holidays['Year'].astype(
            str).isin(selected_years)]

        # Filter by center if applicable
        if selected_center != "All Centers" and 'Center' in filtered_holidays.columns:
            filtered_holidays = filtered_holidays[filtered_holidays['Center']
                                                  == selected_center]
        elif selected_center != "All Centers":
            # Show center info even if not in holiday_df directly
            st.info(f"Showing data for center: {selected_center}")

        # Only keep "All Centers" entries if showing all centers
        if 'Center' in filtered_holidays.columns and selected_center == "All Centers":
            filtered_holidays = filtered_holidays[~filtered_holidays['Center'].notna(
            )]

        # If no data after filtering
        if filtered_holidays.empty:
            st.warning(
                f"No holiday data available for the selected filters. Please try different selections.")
        else:
            # Create bar chart for festivals comparison
            fig_holidays = create_bar_chart(
                filtered_holidays,
                x='Festivals',
                y='MTD_Sale',
                color='Year',
                title="Sales Performance on Holidays",
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
                hovertemplate='₹%{y:,.0f}<extra></extra>'
            )

            st.plotly_chart(fig_holidays, use_container_width=True)

        # Analyze selected festival performance
        if selected_festival:
            st.subheader(f"Detailed Analysis: {selected_festival}")

            # Get the dates of the selected festival for each year
            festival_dates = holiday_df[holiday_df['Festivals']
                                        == selected_festival]['Date']

            # Filter sales data by center if specific center selected
            center_filtered_sales = raw_sales_data
            if selected_center != "All Centers":
                center_filtered_sales = raw_sales_data[raw_sales_data['center_name']
                                                       == selected_center]

            # Create date ranges for analysis (±3 days)
            analysis_data = []

            for festival_date in festival_dates:
                year = festival_date.year

                if str(year) in selected_years:
                    start_date = festival_date - pd.Timedelta(days=3)
                    end_date = festival_date + pd.Timedelta(days=2)

                    # Filter raw sales data for the date range
                    date_range_data = center_filtered_sales[
                        (center_filtered_sales['sale_date'] >= start_date) &
                        (center_filtered_sales['sale_date'] <= end_date)
                    ]

                    if not date_range_data.empty:
                        # Calculate daily totals
                        daily_sales = date_range_data.groupby('sale_date').agg({
                            'sales_collected_exc_tax': 'sum'
                        }).reset_index()

                        # Add festival information
                        daily_sales['Festival'] = selected_festival
                        daily_sales['Festival Date'] = festival_date
                        daily_sales['Year'] = daily_sales['sale_date'].dt.year
                        daily_sales['Formatted Date'] = daily_sales['sale_date'].dt.strftime(
                            '%d %b')
                        analysis_data.append(daily_sales)

            if analysis_data:
                # Combine all analysis data
                combined_analysis = pd.concat(analysis_data)

                # Create histogram with actual dates on x-axis
                fig_analysis = create_bar_chart(
                    combined_analysis,
                    x='Formatted Date',
                    y='sales_collected_exc_tax',
                    color='Year',
                    title=f"Daily Sales Around {selected_festival}",
                    barmode='group'
                )

                # Add annotations to show festival date
                for festival_date in festival_dates:
                    year = festival_date.year
                    if str(year) in selected_years:
                        formatted_date = festival_date.strftime('%d %b')
                        fig_analysis = add_vertical_line(
                            fig_analysis,
                            x=formatted_date,
                            line_color="red",
                            line_width=2,
                            line_dash="dash",
                            annotation_text=f"Festival Day ({formatted_date})",
                            annotation_position="top right"
                        )

                # Update labels and layout
                fig_analysis.update_layout(
                    xaxis_title='Date',
                    yaxis_title='Sales',
                    xaxis={'categoryorder': 'category ascending'},
                    height=500
                )

                fig_analysis.update_traces(
                    hovertemplate='₹%{y:,.0f}<extra></extra>'
                )

                st.plotly_chart(fig_analysis, use_container_width=True)

                # Create performance summary table
                st.subheader("Best Performing Holidays (±3 Days Window)")

                # Calculate total sales for each festival window by center
                festival_performance = []

                for festival in holiday_df['Festivals'].unique():
                    festival_dates = holiday_df[holiday_df['Festivals']
                                                == festival]['Date']

                    for festival_date in festival_dates:
                        year = festival_date.year

                        if str(year) in selected_years:
                            start_date = festival_date - pd.Timedelta(days=3)
                            end_date = festival_date + pd.Timedelta(days=2)

                            # Filter based on selected center
                            if selected_center != "All Centers":
                                center_sales = center_filtered_sales[
                                    (center_filtered_sales['sale_date'] >= start_date) &
                                    (center_filtered_sales['sale_date']
                                     <= end_date)
                                ]
                                center_name = selected_center
                                window_sales = center_sales['sales_collected_exc_tax'].sum(
                                )

                                if window_sales > 0:  # Only add if there are sales
                                    festival_performance.append({
                                        'Festival': festival,
                                        'Year': year,
                                        'Date': festival_date,
                                        'Center': center_name,
                                        'Total Window Sales': window_sales,
                                        'Average Daily Sales': window_sales / 6  # 6 days window
                                    })
                            else:
                                # If all centers, calculate for each center separately
                                for center in raw_sales_data['center_name'].unique():
                                    center_sales = raw_sales_data[
                                        (raw_sales_data['center_name'] == center) &
                                        (raw_sales_data['sale_date'] >= start_date) &
                                        (raw_sales_data['sale_date']
                                         <= end_date)
                                    ]
                                    window_sales = center_sales['sales_collected_exc_tax'].sum(
                                    )

                                    if window_sales > 0:  # Only add if there are sales
                                        festival_performance.append({
                                            'Festival': festival,
                                            'Year': year,
                                            'Date': festival_date,
                                            'Center': center,
                                            'Total Window Sales': window_sales,
                                            'Average Daily Sales': window_sales / 6  # 6 days window
                                        })

                if festival_performance:
                    # Create DataFrame and sort by total sales
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
                else:
                    st.info(f"No sales data found for the selected criteria.")
            else:
                st.info(
                    f"No sales data found around {selected_festival} for the selected years and center.")
    else:
        st.error("Sales data is required for holiday analysis.")
