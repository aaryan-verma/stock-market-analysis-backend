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
    
    # Check if levels are properly calculated (not just zero values)
    valid_level_count = sum(1 for v in levels.values() if v is not None and v > 0)
    logger.debug(f"Valid level count: {valid_level_count} out of {len(levels)}")
    
    # Safety check - ensure all levels have valid values
    for key, value in levels.items():
        if value is None:
            levels[key] = 0
    
    # Ensure last_close is a float
    if last_close is None:
        last_close = 0.0
    
    # Basic validation - only proceed if we have meaningful data'
    if last_close <= 0:
        logger.warning("Cannot interpret zero or negative closing price")
        return "Insufficient data for price interpretation"
    
    # If we have at least R3 and S3, we can provide a basic interpretation
    if 'R3' in levels and levels['R3'] > 0 and 'S3' in levels and levels['S3'] > 0:
        logger.debug("Using basic levels for interpretation")
        
        # Calculate distance to key levels
        r3_diff = (levels['R3'] - last_close) / last_close * 100  # % distance to R3
        s3_diff = (last_close - levels['S3']) / last_close * 100  # % distance to S3
        
        # Create interpretation based on relative position to these levels
        if last_close > levels['R3']:
            return """BULLISH MOMENTUM:
• Price is above resistance level R3
• Interpretation: Strong bullish momentum
• Strategy: Hold positions with trailing stop-loss
• Watch for potential profit-booking at higher levels"""
        elif last_close < levels['S3']:
            return """BEARISH MOMENTUM:
• Price is below support level S3
• Interpretation: Strong bearish momentum
• Strategy: Consider hedging long positions
• Watch for potential oversold bounce"""
        elif r3_diff < s3_diff:
            # Closer to resistance than support
            return f"""APPROACHING RESISTANCE:
• Price is {r3_diff:.2f}% below R3 resistance
• Interpretation: Bullish with caution
• Strategy: Prepare for potential resistance at R3 level
• Consider partial profit booking near resistance"""
        else:
            # Closer to support than resistance
            return f"""NEAR SUPPORT:
• Price is {s3_diff:.2f}% above S3 support
• Interpretation: Watch for bounce
• Strategy: Consider gradual accumulation near support
• Keep tight stop-loss below S3"""
    
    # We have enough levels for a detailed analysis
    if all(levels.get(key, 0) > 0 for key in ['S3', 'S4', 'R3', 'R4']):
        logger.debug("Using full level set for detailed interpretation")
        
        # Standard scenarios when key levels are available
        if last_close < levels['S3'] and last_close > levels['S4']:
            logger.debug("Identified as BULLISH SCENARIO 1")
            return """BULLISH SCENARIO 1:
• Current Close is below S3 but above S4
• Interpretation: BULLISH
• Target: Can move up to R3
• Strategy: Look for buying opportunities"""
            
        elif last_close < levels['S4'] and levels.get('S6', 0) > 0 and last_close > levels['S6']:
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
            
        elif last_close > levels['R4'] and levels.get('R6', 0) > 0 and last_close < levels['R6']:
            logger.debug("Identified as BULLISH SCENARIO 2")
            return """BULLISH SCENARIO 2:
• Current Close is above R4 but below R5/R6
• Interpretation: BULLISH
• Target: Can rise to R6
• Strategy: Hold longs with trailing stop-loss"""
    
    # Create a basic interpretation with just closing price if all else fails
    logger.debug("Using simplified price-based interpretation")
    # Try to compare today's close to the pivot point
    if 'PP' in levels and levels['PP'] > 0:
        if last_close > levels['PP']:
            buffer_pct = (last_close - levels['PP']) / levels['PP'] * 100
            return f"""ABOVE PIVOT POINT:
• Price is {buffer_pct:.2f}% above pivot
• Interpretation: Bullish bias
• Strategy: Look for long opportunities on dips
• Key level to watch: {levels['PP']:.2f} (pivot point)"""
        else:
            buffer_pct = (levels['PP'] - last_close) / levels['PP'] * 100
            return f"""BELOW PIVOT POINT:
• Price is {buffer_pct:.2f}% below pivot
• Interpretation: Bearish bias
• Strategy: Caution advised for new positions
• Key level to watch: {levels['PP']:.2f} (pivot point)"""
    
    # Absolute last resort - basic analysis
    logger.debug("Price is in transition zone")
    return f"Current price: {last_close:.2f}. Monitor price action for clearer signals."

def create_plot(df: pd.DataFrame, period: str) -> str:
    """Create plot with support and resistance levels"""
    # Set style
    plt.style.use('dark_background')
    
    # Add debugging to track the issue
    logger.debug(f"DataFrame shape before plotting: {df.shape}")
    logger.debug(f"DataFrame columns: {df.columns.tolist()}")
    
    # Ensure we have levels data in the DataFrame
    level_cols = ['PP', 'S3', 'S4', 'S5', 'S6', 'R3', 'R4', 'R5', 'R6']
    
    # First check if we need to force-calculate levels for the last row
    if len(df) > 0:
        last_idx = df.index[-1]
        missing_levels = []
        
        for col in level_cols:
            # Check if the column exists but has a null/zero value
            if col in df.columns and (pd.isna(df.loc[last_idx, col]) or df.loc[last_idx, col] is None or df.loc[last_idx, col] == 0):
                missing_levels.append(col)
        
        if missing_levels:
            logger.warning(f"Missing levels in plot function: {missing_levels}")
            
            # Get data for calculation - preferably from previous row, otherwise from current
            if len(df) > 1:
                calc_row = df.iloc[-2]
            else:
                calc_row = df.iloc[-1]
            
            # Extract OHLC values
            O = float(calc_row['Open'] if calc_row['Open'] is not None else 0)
            H = float(calc_row['High'] if calc_row['High'] is not None else 0)
            L = float(calc_row['Low'] if calc_row['Low'] is not None else 0)
            C = float(calc_row['Close'] if calc_row['Close'] is not None else 0)
            
            # Calculate only if we have valid data
            if H > 0 and L > 0 and C > 0:
                RANGE = H - L
                
                # Calculate and set missing levels
                levels_to_calculate = {
                    'PP': (H + L + C) / 3,
                    'R3': C + RANGE * 1.1/4,
                    'R4': C + RANGE * 1.1/2,
                }
                
                # Set these basic levels first
                for level, value in levels_to_calculate.items():
                    if level in missing_levels:
                        df.loc[last_idx, level] = value
                        logger.debug(f"Plot function set {level} = {value}")
                
                # Calculate derived levels that depend on the basic ones
                if 'R3' in df.columns and 'R4' in df.columns and ('R5' in missing_levels):
                    r3 = df.loc[last_idx, 'R3']
                    r4 = df.loc[last_idx, 'R4']
                    if not pd.isna(r3) and not pd.isna(r4) and r3 > 0 and r4 > 0:
                        df.loc[last_idx, 'R5'] = r4 + 1.168 * (r4 - r3)
                        logger.debug(f"Plot function set R5 = {df.loc[last_idx, 'R5']}")
                
                if 'R6' in missing_levels:
                    df.loc[last_idx, 'R6'] = (H/L) * C
                    logger.debug(f"Plot function set R6 = {df.loc[last_idx, 'R6']}")
                
                if 'S3' in missing_levels:
                    df.loc[last_idx, 'S3'] = C - RANGE * 1.1/4
                    logger.debug(f"Plot function set S3 = {df.loc[last_idx, 'S3']}")
                
                if 'S4' in missing_levels:
                    df.loc[last_idx, 'S4'] = C - RANGE * 1.1/2
                    logger.debug(f"Plot function set S4 = {df.loc[last_idx, 'S4']}")
                
                if 'S3' in df.columns and 'S4' in df.columns and ('S5' in missing_levels):
                    s3 = df.loc[last_idx, 'S3']
                    s4 = df.loc[last_idx, 'S4']
                    if not pd.isna(s3) and not pd.isna(s4) and s3 > 0 and s4 > 0:
                        df.loc[last_idx, 'S5'] = s4 - 1.168 * (s3 - s4)
                        logger.debug(f"Plot function set S5 = {df.loc[last_idx, 'S5']}")
                
                if 'R6' in df.columns and ('S6' in missing_levels):
                    r6 = df.loc[last_idx, 'R6']
                    if not pd.isna(r6) and r6 > 0:
                        df.loc[last_idx, 'S6'] = 2 * C - r6
                        logger.debug(f"Plot function set S6 = {df.loc[last_idx, 'S6']}")
    
    # Ensure we have at least 5 rows to display
    if len(df) < 5:
        logger.warning(f"Not enough data points for visualization: {len(df)}")
        # Create a more informative plot instead
        fig, ax = plt.subplots(figsize=(14, 8), facecolor='#1f2937')
        ax.set_facecolor('#1f2937')
        ax.text(0.5, 0.5, f"Insufficient data for visualization.\nOnly {len(df)} data points available.\nMinimum 5 required.", 
                horizontalalignment='center',
                verticalalignment='center',
                fontsize=14,
                color='white',
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        
        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight', facecolor='#1f2937')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        return image_base64
    
    # Get last 5 data points (or all if less than 5)
    last_5_df = df.tail(min(5, len(df)))
    
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
    
    # Define the levels to plot and their colors and styles
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
    
    # Get the last values from the full dataframe so we include calculated levels for today
    if len(df) > 0:
        # Use the very last row for all levels, even if it's today
        last_values = df.iloc[-1]
        logger.debug(f"Using last row for levels: {last_values.index}")
        
        # Calculate min and max values for y-axis scaling
        all_values = []
        price_range = []
        
        # Add actual price data first
        for col in ['Open', 'High', 'Low', 'Close']:
            if col in last_5_df.columns:
                val_list = last_5_df[col].dropna().tolist()
                logger.debug(f"Price data for {col}: {val_list}")
                price_range.extend(val_list)
        
        # Special debug to check for level values
        if len(last_values) > 0:
            level_debug = {}
            for level in colors.keys():
                if level in last_values.index:
                    level_debug[level] = last_values[level]
            logger.debug(f"Available level values: {level_debug}")
        
        # Plot levels with improved visibility and right-aligned labels
        for level, (color, style, label) in colors.items():
            # Check if level exists in the last row
            if level in last_values.index:
                value = last_values[level]
                
                # Convert to float and check validity
                try:
                    value = float(value) if value is not None else None
                except (TypeError, ValueError):
                    value = None
                
                # Log the level value whether it's valid or not
                logger.debug(f"Level {level} value = {value}, type = {type(value)}")
                
                if value is not None and value > 0 and not np.isinf(value) and not np.isnan(value):
                    # Track the level value for scaling the plot
                    all_values.append(value)
                    
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
                    logger.debug(f"Added level {level} at value {value}")
                else:
                    logger.warning(f"Skipping level {level} due to invalid value: {value}")
            else:
                logger.warning(f"Level {level} not found in last row indices")
        
        # Calculate appropriate y-axis limits based on all values (prices and levels)
        if price_range and all_values:
            # Combine price data and level values for calculating y limits
            all_data_points = price_range + all_values
            min_val = min([v for v in all_data_points if v is not None])
            max_val = max([v for v in all_data_points if v is not None])
            padding = (max_val - min_val) * 0.1  # 10% padding
            
            ax_candles.set_ylim(min_val - padding, max_val + padding)
            logger.debug(f"Y-axis range set to: {min_val - padding} - {max_val + padding}")
    
    # Set x-axis limits
    ax_candles.set_xlim(-0.5, len(last_5_df) - 0.5)
    
    # Add a title with the symbol and date range
    title_dates = f"{dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}"
    symbol = df['Symbol'].iloc[0] if 'Symbol' in df.columns else 'Stock'
    plt.title(f"{symbol} - {title_dates}", fontsize=14, color='white', pad=10)
    
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
    isin: Optional[str] = None,
    is_index: Optional[bool] = False,
    token: str = Depends(verify_token),
):
    """
    Get technical analysis plot with support and resistance levels
    
    Args:
        symbol: Stock symbol
        start_date: Start date in DD-MM-YYYY format
        end_date: End date in DD-MM-YYYY format
        period: Resampling period ('D'=Daily, 'W'=Weekly, 'M'=Monthly, 'Q'=Quarterly, 'Y'=Yearly)
        isin: Optional ISIN number for the stock
        is_index: Optional - Whether the symbol is an index (Nifty 50, Bank Nifty, etc.)
    
    Returns:
        JSON with plot data as base64 string
    """
    logger.info(f"Visualization request for symbol: {symbol}, period: {period}, is_index: {is_index}")
    try:
        # Get stock data
        logger.debug(f"Fetching stock data for visualization of {symbol}")
        stock_data = await get_stock_data(symbol, start_date, end_date, period, isin, is_index)
        
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
        
        # Check if we have enough data to proceed
        if len(resampled_data) < 2:
            logger.warning(f"Not enough data points after resampling: {len(resampled_data)}")
            raise HTTPException(
                status_code=400,
                detail=f"Not enough data points to generate visualization. Need at least 2 {valid_periods[period].lower()} candles."
            )
        
        logger.debug("Calculating support and resistance levels for visualization")
        analysis_result = calculate_levels(resampled_data)
        
        # Guaranteed level calculation for the last trading day
        logger.info("Performing guaranteed level calculation for last trading day")
        if len(analysis_result) > 0:
            last_idx = analysis_result.index[-1]
            
            # Get the data for the last day
            last_row = analysis_result.iloc[-1]
            
            # Get historical data for calculations - use either last day or day before
            if len(analysis_result) > 1:
                prev_idx = analysis_result.index[-2]
                calc_row = analysis_result.loc[prev_idx]
            else:
                calc_row = last_row
                
            # Ensure we have OHLC data
            O = float(calc_row['Open'] if calc_row['Open'] is not None else 0)
            H = float(calc_row['High'] if calc_row['High'] is not None else 0)
            L = float(calc_row['Low'] if calc_row['Low'] is not None else 0)
            C = float(calc_row['Close'] if calc_row['Close'] is not None else 0)
            
            # Only calculate if we have valid data
            if O > 0 and H > 0 and L > 0 and C > 0:
                logger.info(f"Calculating levels using O={O}, H={H}, L={L}, C={C}")
                
                # Calculate Range
                RANGE = H - L
                
                # Create a new dict to hold level values
                level_values = {}
                
                # Calculate all levels
                level_values['PP'] = (H + L + C) / 3
                
                # Resistance levels
                level_values['R3'] = C + RANGE * 1.1/4
                level_values['R4'] = C + RANGE * 1.1/2
                level_values['R6'] = (H/L) * C
                level_values['R5'] = level_values['R4'] + 1.168 * (level_values['R4'] - level_values['R3'])
                
                # Support levels
                level_values['S3'] = C - RANGE * 1.1/4
                level_values['S4'] = C - RANGE * 1.1/2
                level_values['S5'] = level_values['S4'] - 1.168 * (level_values['S3'] - level_values['S4'])
                level_values['S6'] = 2 * C - level_values['R6']
                
                # Apply these values to the last row
                for level, value in level_values.items():
                    if pd.isna(analysis_result.loc[last_idx, level]) or analysis_result.loc[last_idx, level] is None or analysis_result.loc[last_idx, level] == 0:
                        analysis_result.loc[last_idx, level] = value
                        logger.debug(f"Set {level} = {value} for last trading day")
                    else:
                        logger.debug(f"Kept existing {level} = {analysis_result.loc[last_idx, level]} for last trading day")
                
                # Check that we now have valid levels
                level_cols = ['PP', 'R3', 'R4', 'S3', 'S4']
                valid_levels = sum(1 for col in level_cols if col in analysis_result.columns and not pd.isna(analysis_result.loc[last_idx, col]) and analysis_result.loc[last_idx, col] > 0)
                logger.info(f"Last trading day now has {valid_levels} valid levels out of {len(level_cols)} basic levels")
                
                # Final validation log message
                if valid_levels < len(level_cols):
                    missing_levels = [col for col in level_cols if col in analysis_result.columns and (pd.isna(analysis_result.loc[last_idx, col]) or analysis_result.loc[last_idx, col] <= 0)]
                    logger.warning(f"Still missing levels after calculations: {missing_levels}")
        
        # Get last closing price and levels
        last_close = analysis_result['Close'].iloc[-1]
        last_values = analysis_result.iloc[-1]
        
        # Safely extract level values with fallbacks to avoid NoneType errors
        levels = {}
        for level in ['R6', 'R5', 'R4', 'R3', 'PP', 'S3', 'S4', 'S5', 'S6']:
            value = last_values.get(level)
            # Convert None to float to avoid comparison issues
            levels[level] = float(value) if value is not None else 0.0
        
        # Ensure last_close is a float
        last_close = float(last_close) if last_close is not None else 0.0
        
        interpretation = get_closing_interpretation(last_close, levels)
        plot_base64 = create_plot(analysis_result, period)
        
        # Get last candle data with safety checks
        last_candle = analysis_result.iloc[-1]
        
        # Safely extract OHLC values with fallbacks
        date_str = last_candle.name.strftime('%Y-%m-%d') if hasattr(last_candle.name, 'strftime') else 'N/A'
        open_val = float(last_candle['Open']) if last_candle['Open'] is not None else 0.0
        high_val = float(last_candle['High']) if last_candle['High'] is not None else 0.0
        low_val = float(last_candle['Low']) if last_candle['Low'] is not None else 0.0
        close_val = float(last_candle['Close']) if last_candle['Close'] is not None else 0.0
        
        # Calculate change percentage safely
        if open_val > 0:
            change_pct = ((close_val - open_val) / open_val) * 100
        else:
            change_pct = 0.0
        
        last_ohlc = {
            "date": date_str,
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
            "change": change_pct
        }
        
        logger.info(f"Successfully created visualization for {symbol}")
        
        # Truncate base64 plot data for logging purposes only
        log_plot = plot_base64[:50] + "..." if len(plot_base64) > 50 else plot_base64
        logger.debug(f"Generated plot data (truncated): {log_plot}")
        
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
