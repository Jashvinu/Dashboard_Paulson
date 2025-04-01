import pandas as pd
import streamlit as st


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


def format_percentage(value, include_sign=True):
    """Format a decimal value as a percentage"""
    if pd.isna(value):
        return "0%"

    formatted = f"{value:.2f}"
    if include_sign:
        return f"{formatted}%"
    return formatted


def create_month_order():
    """Return the standard month order for consistent sorting"""
    return ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December']


def add_month_sorting_column(df, month_column='Month'):
    """Add a sorting column based on month names"""
    month_order = create_month_order()
    df['Month_Sorted'] = pd.Categorical(
        df[month_column],
        categories=month_order,
        ordered=True
    )
    return df


def format_dataframe_currency(df, columns):
    """Format multiple currency columns in a dataframe"""
    formatted_df = df.copy()
    for col in columns:
        if col in formatted_df.columns:
            formatted_df[col] = formatted_df[col].apply(format_indian_money)
    return formatted_df
