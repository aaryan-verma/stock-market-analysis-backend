from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import numpy as np
from app.api.endpoints.stock_data import get_stock_data
from app.utils.technical_analysis import data_resampling, calculate_levels
from app.api.deps import create_token_auth_router, verify_token
from app.api.logger import get_logger

# Set up logger for this module
logger = get_logger(__name__)

router = create_token_auth_router()

def get_closing_interpretation(last_close: float, levels: dict) -> str:
    """Get interpretation based on closing price"""
    logger.debug(f"Interpreting closing price: {last_close}")
    if last_close < levels['S3'] and last_close > levels['S4']:
        logger.debug("Identified as BULLISH SCENARIO 1")
        return """BULLISH SCENARIO 1:
• Current Close is below S3 but above S4
• Interpretation: BULLISH
• Target: Can move up to R3
• Strategy: Look for buying opportunities"""
        
    elif last_close < levels['S4'] and last_close > levels['S6']:
        logger.debug("Identified as BEARISH SCENARIO 1")
        return """BEARISH SCENARIO 1:
• Current Close is below S4 (above S5/S6)
• Interpretation: BEARISH
• Target: Can fall to S6
• Strategy: Watch for selling opportunities"""
        
    elif last_close > levels['R3'] and last_close < levels['R4']:
        logger.debug("Identified as BEARISH SCENARIO 2")
        return """BEARISH SCENARIO 2:
• Current Close is above R3 but below R4
• Interpretation: BEARISH
• Target: Can fall to S3
• Strategy: Consider profit booking/shorts"""
        
    elif last_close > levels['R4'] and last_close < levels['R6']:
        logger.debug("Identified as BULLISH SCENARIO 2")
        return """BULLISH SCENARIO 2:
• Current Close is above R4 but below R5/R6
• Interpretation: BULLISH
• Target: Can rise to R6
• Strategy: Hold longs with trailing stop-loss"""
    
    logger.debug("Price is in transition zone")
    return "Price is in transition zone. Wait for clear signals."

def create_plot(df: pd.DataFrame, period: str) -> str:
    """Create plot with support and resistance levels"""
    # Set style
    plt.style.use('dark_background')
    
    # Get last 5 data points
    last_5_df = df.tail(5)
    
    # Create figure with subplots: one for candlesticks, one for table
    fig = plt.figure(figsize=(14, 8), facecolor='#1f2937')  # Reduced height
    
    # Create grid spec to control subplot sizes
    gs = fig.add_gridspec(1, 1, height_ratios=[3], hspace=0.3)  # Changed to 1 subplot
    
    # Candlestick subplot
    ax_candles = fig.add_subplot(gs[0])
    ax_candles.set_facecolor('#1f2937')
    ax_candles.grid(False)
    
    # Create numerical x-coordinates
    x_coords = range(len(last_5_df))
    dates = last_5_df.index
    
    # Plot candlesticks
    for i, (idx, row) in enumerate(last_5_df.iterrows()):
        # Calculate candle position and size
        x = i  # Use numerical index instead of timestamp
        open_price = row['Open']
        close_price = row['Close']
        high_price = row['High']
        low_price = row['Low']
        
        # Determine if it's a bullish or bearish candle
        if close_price >= open_price:
            color = '#22c55e'  # Green for bullish
            body_color = color
        else:
            color = '#ef4444'  # Red for bearish
            body_color = color
        
        # Plot the wick (high-low range)
        ax_candles.plot([x, x], [low_price, high_price], 
                color=color, 
                linewidth=1.5,
                zorder=5)
        
        # Plot the body (open-close range)
        body_height = abs(open_price - close_price)
        body_bottom = min(open_price, close_price)
        
        # Make sure body has minimum height for visibility
        if body_height < 0.001:
            body_height = 0.001
            
        ax_candles.add_patch(plt.Rectangle(
            (x - 0.3, body_bottom),
            0.6, body_height,
            fill=True,
            color=body_color,
            alpha=1,
            zorder=6
        ))
        
        # Add price labels above each candle
        label_y = high_price
        ax_candles.annotate(f'₹{close_price:,.2f}', 
                   (x, label_y), 
                   textcoords="offset points", 
                   xytext=(0, 15), 
                   ha='center',
                   color='white',
                   fontweight='bold',
                   bbox=dict(
                       facecolor=color,
                       edgecolor='none',
                       alpha=0.7,
                       pad=3,
                       boxstyle='round,pad=0.5'
                   ))
    
    # Format axes for candlestick plot
    plt.sca(ax_candles)
    plt.xticks(x_coords, 
               [d.strftime('%Y-%m-%d') for d in dates], 
               rotation=30, 
               ha='right',
               color='white')
    
    ax_candles.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x:,.2f}'))
    ax_candles.tick_params(axis='y', colors='white')
    
    # Get the last values for each level
    last_values = last_5_df.iloc[-1]
    symbol = last_5_df['Symbol'].iloc[0] if 'Symbol' in last_5_df.columns else 'Stock'
    
    # Plot levels with modern styling
    colors = {
        'R6': ('#22c55e', ':', 'Target 2 LONG'),    # Green
        'R5': ('#22c55e', '--', 'Target 1 LONG'),
        'R4': ('#22c55e', '-', 'Breakout'),
        'R3': ('#94a3b8', '-', 'Sell reversal'),    # Gray
        'PP': ('#f59e0b', '--', 'Pivot Point'),     # Orange
        'S3': ('#94a3b8', '-', 'Buy reversal'),
        'S4': ('#ef4444', '-', 'Breakdown'),        # Red
        'S5': ('#ef4444', '--', 'Target 1 SHORT'),
        'S6': ('#ef4444', ':', 'Target 2 SHORT')
    }
    
    # Get plot boundaries for the last candle
    x_start = len(last_5_df) - 1  # Start from the last candle
    x_max = len(last_5_df) - 0.5  # End slightly after the last candle
    
    # Plot levels with improved visibility and right-aligned labels
    for level, (color, style, label) in colors.items():
        if level in last_values.index:
            value = last_values[level]
            if pd.notnull(value) and not np.isinf(value):
                # Draw the level line only from the last candle
                ax_candles.plot([x_start, x_max + 0.5], [value, value],
                       color=color,
                       linestyle=style,
                       alpha=0.8,
                       linewidth=1.5,
                       zorder=4)
                
                # Add label on the right
                ax_candles.annotate(f'{level} ({label}): ₹{value:,.2f}',
                          xy=(x_max, value),
                          xytext=(5, 0),
                          textcoords='offset points',
                          ha='left',
                          va='center',
                          color=color,
                          fontweight='bold',
                          bbox=dict(
                              facecolor='#1f2937',
                              edgecolor=color,
                              alpha=0.9,
                              pad=3,
                              boxstyle='round,pad=0.5'
                          ))
    
    # Set x-axis limits
    ax_candles.set_xlim(-0.5, len(last_5_df) - 0.5)
    
    # Convert plot to base64 string with higher DPI
    buffer = io.BytesIO()
    plt.savefig(buffer, 
                format='png', 
                dpi=300, 
                bbox_inches='tight',
                facecolor='#1f2937',
                edgecolor='none')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    logger.debug("Visualization plot created successfully")
    return image_base64

@router.get("/plot/{symbol}")
async def get_technical_analysis_plot(
    symbol: str,
    start_date: str,
    end_date: str,
    period: Optional[str] = "D",
    token: str = Depends(verify_token),
):
    """
    Get technical analysis plot with support and resistance levels
    
    Args:
        symbol: Stock symbol
        start_date: Start date in DD-MM-YYYY format
        end_date: End date in DD-MM-YYYY format
        period: Resampling period ('D'=Daily, 'W'=Weekly, 'M'=Monthly, 'Q'=Quarterly, 'Y'=Yearly)
    
    Returns:
        JSON with plot data as base64 string
    """
    logger.info(f"Visualization request for symbol: {symbol}, period: {period}")
    try:
        # Get stock data
        logger.debug(f"Fetching stock data for visualization of {symbol}")
        stock_data = await get_stock_data(symbol, start_date, end_date)
        
        if not stock_data["data"]:
            logger.warning(f"No data found for visualization of symbol {symbol}")
            raise HTTPException(
                status_code=404,
                detail=f"No data found for symbol {symbol} in the specified date range"
            )
        
        df = pd.DataFrame(stock_data['data'])
        logger.debug(f"Retrieved {len(df)} data points for visualization")
        
        # Make sure we have dates in the proper format
        try:
            # If the Date column exists but contains null values, create a range of dates
            if 'Date' in df.columns and df['Date'].isnull().any():
                logger.debug("Date column contains null values, generating date range")
                # Parse start and end dates
                start = pd.to_datetime(start_date, format='%d-%m-%Y')
                end = pd.to_datetime(end_date, format='%d-%m-%Y')
                # Create date range that matches the number of rows
                date_range = pd.date_range(start=start, end=end, periods=len(df))
                df['Date'] = date_range
            
            # If Date column doesn't exist, create it
            if 'Date' not in df.columns:
                logger.debug("Date column doesn't exist, generating date range")
                # Parse start and end dates
                start = pd.to_datetime(start_date, format='%d-%m-%Y')
                end = pd.to_datetime(end_date, format='%d-%m-%Y')
                # Create date range that matches the number of rows
                date_range = pd.date_range(start=start, end=end, periods=len(df))
                df['Date'] = date_range
            
            # Ensure Date is datetime
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            # Drop rows with invalid dates
            invalid_date_count = df['Date'].isna().sum()
            if invalid_date_count > 0:
                logger.warning(f"Dropping {invalid_date_count} rows with invalid dates")
                df = df.dropna(subset=['Date'])
            
            # Set Date as index
            df = df.set_index('Date')
            
            # Debug column names and data types
            logger.debug(f"DataFrame columns: {df.columns.tolist()}")
            logger.debug(f"DataFrame dtypes: {df.dtypes}")
            
        except Exception as e:
            logger.error(f"Error processing dates: {str(e)}", exc_info=True)
            # Generate synthetic dates as a fallback
            logger.debug("Using synthetic date range as fallback")
            date_range = pd.date_range(start='today', periods=len(df))
            df = df.set_index(date_range)
        
        # Validate period
        valid_periods = {'D': 'Daily', 'W': 'Weekly', 'M': 'Monthly', 'Q': 'Quarterly', 'Y': 'Yearly'}
        if period not in valid_periods:
            logger.warning(f"Invalid period specified: {period}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period. Must be one of: {', '.join(valid_periods.keys())}"
            )
        
        # Process data
        logger.debug(f"Resampling data for visualization to {valid_periods[period]} period")
        resampled_data = data_resampling(df, period)
        
        logger.debug("Calculating support and resistance levels for visualization")
        analysis_result = calculate_levels(resampled_data)
        
        # Get last closing price and levels
        last_close = analysis_result['Close'].iloc[-1]
        last_values = analysis_result.iloc[-1]
        levels = {
            'R6': last_values['R6'],
            'R5': last_values['R5'],
            'R4': last_values['R4'],
            'R3': last_values['R3'],
            'PP': last_values['PP'],
            'S3': last_values['S3'],
            'S4': last_values['S4'],
            'S5': last_values['S5'],
            'S6': last_values['S6']
        }
        
        interpretation = get_closing_interpretation(last_close, levels)
        plot_base64 = create_plot(analysis_result, period)
        
        # Get last candle data
        last_candle = analysis_result.iloc[-1]
        last_ohlc = {
            "date": last_candle.name.strftime('%Y-%m-%d'),
            "open": float(last_candle['Open']),
            "high": float(last_candle['High']),
            "low": float(last_candle['Low']),
            "close": float(last_candle['Close']),
            "change": float((last_candle['Close'] - last_candle['Open']) / last_candle['Open'] * 100)
        }
        
        logger.info(f"Successfully created visualization for {symbol}")
        return JSONResponse({
            "symbol": symbol,
            "period": valid_periods[period],
            "start_date": start_date,
            "end_date": end_date,
            "plot": plot_base64,
            "interpretation": interpretation,
            "last_ohlc": last_ohlc
        })
        
    except Exception as e:
        logger.error(f"Error generating visualization for {symbol}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Plot generation failed: {str(e)}"
        )
