import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import streamlit as st
from format_utils import format_indian_money


def create_bar_chart(data, x, y, title, color=None,
                     color_continuous_scale='Viridis',
                     text_format=None,
                     height=None,
                     barmode='group',
                     category_orders=None):
    """Create a standardized bar chart for the dashboard"""

    # Apply formatting for hover text if provided
    if text_format == 'money':
        hover_text = data[y].apply(format_indian_money)
    elif text_format == 'int':
        hover_text = data[y].apply(lambda x: f"{int(x):,}")
    elif text_format:
        hover_text = data[y].apply(text_format)
    else:
        hover_text = None

    # Create the chart
    fig = px.bar(
        data,
        x=x,
        y=y,
        color=color,
        barmode=barmode,
        title=title,
        color_continuous_scale=color_continuous_scale,
        category_orders=category_orders,
        height=height,
        text=hover_text
    )

    # Update the layout
    fig.update_layout(
        xaxis_title=x if isinstance(x, str) else None,
        yaxis_title=y if isinstance(y, str) else None
    )

    # Update the traces
    if hover_text is not None:
        fig.update_traces(
            textposition='outside',
            hovertemplate='%{text}<extra></extra>'
        )

    return fig


def create_line_chart(data, x, y, title, color=None, line_group=None,
                      markers=True, text_format=None, height=None,
                      category_orders=None):
    """Create a standardized line chart for the dashboard"""

    # Apply formatting for hover text if provided
    if text_format == 'money':
        hover_text = data[y].apply(format_indian_money)
    elif text_format == 'int':
        hover_text = data[y].apply(lambda x: f"{int(x):,}")
    elif text_format:
        hover_text = data[y].apply(text_format)
    else:
        hover_text = None

    # Create the chart
    fig = px.line(
        data,
        x=x,
        y=y,
        color=color,
        line_group=line_group,
        markers=markers,
        title=title,
        category_orders=category_orders,
        height=height
    )

    # Update the layout
    fig.update_layout(
        xaxis_title=x if isinstance(x, str) else None,
        yaxis_title=y if isinstance(y, str) else None
    )

    # Update the traces for hover text
    if hover_text is not None:
        fig.update_traces(
            hovertemplate='%{text}<extra></extra>',
            text=hover_text
        )

    return fig


def create_pie_chart(data, values, names, title, hole=0.4,
                     color_discrete_sequence=px.colors.qualitative.Pastel,
                     text_format=None, height=None):
    """Create a standardized pie chart for the dashboard"""

    # Apply formatting for hover text if provided
    if text_format == 'money':
        hover_text = data[values].apply(format_indian_money).apply(
            lambda x: x.replace('₹', ''))
    elif text_format == 'int':
        hover_text = data[values].apply(lambda x: f"{int(x):,}")
    elif text_format:
        hover_text = data[values].apply(text_format)
    else:
        hover_text = None

    # Create the chart
    fig = px.pie(
        data,
        values=values,
        names=names,
        title=title,
        hole=hole,
        color_discrete_sequence=color_discrete_sequence,
        height=height
    )

    # Update the traces
    if hover_text is not None:
        fig.update_traces(
            texttemplate='%{label}<br>₹%{text}',
            text=hover_text,
            hovertemplate='₹%{text}<extra></extra>'
        )
    else:
        fig.update_traces(
            texttemplate='%{label}<br>%{value:,.0f}',
            hovertemplate='%{label}<br>%{value:,.0f}<extra></extra>'
        )

    return fig


def create_treemap(data, path, values, title, color=None,
                   color_continuous_scale='Viridis',
                   text_format=None, height=None):
    """Create a standardized treemap for the dashboard"""

    # Apply formatting for custom data if provided
    if text_format == 'money':
        custom_data = [data[values].apply(
            format_indian_money).apply(lambda x: x.replace('₹', ''))]
    elif text_format == 'int':
        custom_data = [data[values].apply(lambda x: f"{int(x):,}")]
    elif text_format:
        custom_data = [data[values].apply(text_format)]
    else:
        custom_data = None

    # Create the chart
    fig = px.treemap(
        data,
        path=path,
        values=values,
        title=title,
        color=color,
        color_continuous_scale=color_continuous_scale,
        height=height,
        custom_data=custom_data
    )

    # Update the traces
    if custom_data is not None:
        fig.update_traces(
            texttemplate='%{label}<br>₹%{customdata[0]}',
            hovertemplate='%{label}<br>Total: ₹%{customdata[0]}<extra></extra>'
        )

    return fig


def display_metric_cards(metrics_data, num_columns=4):
    """Display a set of metric cards in columns"""
    columns = st.columns(num_columns)

    for i, (title, value, delta, delta_color, help_text) in enumerate(metrics_data):
        # Set a default value for delta_color if None is provided
        if delta_color is None:
            delta_color = 'normal'

        with columns[i % num_columns]:
            st.metric(
                label=title,
                value=value,
                delta=delta,
                delta_color=delta_color,
                help=help_text
            )


def add_vertical_line(fig, x_value, line_color="red", line_width=2, line_dash="dash", annotation_text=None, annotation_position="top right"):
    """Add a vertical line to a Plotly figure with optional annotation"""
    fig.add_vline(
        x=x_value,
        line_color=line_color,
        line_width=line_width,
        line_dash=line_dash
    )

    if annotation_text:
        fig.add_annotation(
            x=x_value,
            y=1,
            yref="paper",
            text=annotation_text,
            showarrow=False,
            xanchor="right" if annotation_position.endswith(
                "right") else "left",
            yanchor="top" if annotation_position.startswith(
                "top") else "bottom"
        )

    return fig
