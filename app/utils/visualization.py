import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import io
import base64
from typing import Dict, Tuple, Optional
import matplotlib
import gc

def setup_plot_style(figsize: Tuple[int, int] = (12, 6), dpi: int = 100) -> Tuple[plt.Figure, plt.Axes]:
    """
    Setup the basic plot style and figure
    
    Args:
        figsize: Figure size as (width, height)
        dpi: Dots per inch for the figure
    
    Returns:
        Tuple of (figure, axis)
    """
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    return fig, ax

def get_level_styles() -> Dict[str, Tuple[str, str, str]]:
    """
    Get the styling configuration for different levels
    
    Returns:
        Dictionary of level styles with (color, line style, label)
    """
    return {
        'R6': ('green', ':', 'Target 2 LONG'),
        'R5': ('green', '--', 'Target 1 LONG'),
        'R4': ('green', '-', 'Breakout'),
        'R3': ('black', '-', 'Sell reversal'),
        'PP': ('gray', '--', 'Pivot Point'),
        'S3': ('black', '-', 'Buy reversal'),
        'S4': ('red', '-', 'Breakdown'),
        'S5': ('red', '--', 'Target 1 SHORT'),
        'S6': ('red', ':', 'Target 2 SHORT')
    }

def plot_price_data(ax: plt.Axes, df: pd.DataFrame, color: str = 'blue', linewidth: float = 1):
    """
    Plot the close price data
    
    Args:
        ax: Matplotlib axis
        df: DataFrame with price data
        color: Line color
        linewidth: Line width
    """
    ax.plot(df.index, df['Close'], label='Close Price', color=color, linewidth=linewidth)

def plot_levels(ax: plt.Axes, df: pd.DataFrame, level_styles: Dict[str, Tuple[str, str, str]]):
    """
    Plot support and resistance levels
    
    Args:
        ax: Matplotlib axis
        df: DataFrame with level data
        level_styles: Dictionary of level styles
    """
    last_values = df.iloc[-1]
    
    for level, (color, style, label) in level_styles.items():
        if level in last_values.index:
            value = last_values[level]
            if pd.notnull(value) and not np.isinf(value):
                ax.axhline(y=value, color=color, linestyle=style, 
                          label=f'{level} ({label}): {value:.2f}')

def customize_plot(ax: plt.Axes, title: str, rotate_labels: bool = True):
    """
    Customize plot appearance
    
    Args:
        ax: Matplotlib axis
        title: Plot title
        rotate_labels: Whether to rotate x-axis labels
    """
    ax.set_title(title, fontsize=12)
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    ax.grid(True, alpha=0.3)
    
    if rotate_labels:
        plt.xticks(rotation=45)
    
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)

def convert_plot_to_base64(fig: plt.Figure, dpi: int = 300) -> str:
    """
    Convert matplotlib figure to base64 string
    
    Args:
        fig: Matplotlib figure
        dpi: Dots per inch for the output
    
    Returns:
        Base64 encoded string of the plot
    """
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=dpi, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    return image_base64

def create_technical_analysis_plot(
    df: pd.DataFrame,
    period: str,
    figsize: Tuple[int, int] = (12, 6),
    dpi: int = 100
) -> str:
    """
    Create technical analysis plot with support and resistance levels
    
    Args:
        df: DataFrame with price and level data
        period: Analysis period (e.g., 'Daily', 'Weekly')
        figsize: Figure size as (width, height)
        dpi: Dots per inch for the figure
    
    Returns:
        Base64 encoded string of the plot
    """
    # Use Agg backend (memory efficient)
    matplotlib.use('Agg')
    
    # Clear any existing plots
    plt.close('all')
    
    # Reduce DPI and figure size for memory savings
    fig, ax = setup_plot_style(figsize=(8, 4), dpi=80)
    
    try:
        # Plot price data
        plot_price_data(ax, df)
        
        # Plot levels
        level_styles = get_level_styles()
        plot_levels(ax, df, level_styles)
        
        # Customize plot
        symbol = df['Symbol'].iloc[0] if 'Symbol' in df.columns else 'Stock'
        title = f'{symbol} - {period} Analysis'
        customize_plot(ax, title)
        
        # Adjust layout
        plt.tight_layout()
        
        # Convert to base64
        return convert_plot_to_base64(fig)
    finally:
        # Ensure cleanup
        plt.close(fig)
        gc.collect() 