import pandas as pd
import numpy as np

def data_resampling(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """
    Resample data to specified period
    
    Args:
        df: DataFrame with OHLC data
        period: Resampling period ('D'=Daily, 'W'=Weekly, 'M'=Monthly, 'Q'=Quarterly, 'Y'=Yearly)
    
    Returns:
        Resampled DataFrame
    """
    # Check if Date is already in the index
    if not isinstance(df.index, pd.DatetimeIndex):
        # If Date is a column, try to set it as index
        if 'Date' in df.columns:
            # Convert to datetime if needed
            if not pd.api.types.is_datetime64_any_dtype(df['Date']):
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.set_index('Date')
        else:
            # If no Date column exists, create a dummy datetime index
            df.index = pd.date_range(start='today', periods=len(df))
    
    logic = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Symbol': 'first'  # Keep the symbol
    }
    
    # Resample with inclusive end date
    dfw = df.resample(period, closed='right', label='right').apply(logic)
    
    return dfw

def calculate_levels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate support and resistance levels
    
    Args:
        df: DataFrame with OHLC data
    
    Returns:
        DataFrame with calculated levels
    """
    T = df.copy()
    
    # Initialize new columns
    levels = ['PP', 'S3', 'S4', 'S5', 'S6', 'R3', 'R4', 'R5', 'R6']
    for level in levels:
        T[level] = pd.NA  # Use pandas NA instead of np.nan
    
    # Fill numeric columns with 0 and non-numeric with appropriate values
    T = T.fillna({
        'Open': 0,
        'High': 0,
        'Low': 0,
        'Close': 0,
        'Symbol': T['Symbol'].iloc[0] if 'Symbol' in T.columns else 'Stock'
    })
    
    for x in range(len(T)-1):
        # Use iloc instead of direct indexing
        O = T['Open'].iloc[x]
        C = T['Close'].iloc[x]
        L = T['Low'].iloc[x]
        H = T['High'].iloc[x]
        RANGE = H-L
        
        next_idx = T.index[x+1]
        
        # Calculate resistance levels
        T.loc[next_idx, 'R3'] = C + RANGE * 1.1/4
        T.loc[next_idx, 'R4'] = C + RANGE * 1.1/2
        T.loc[next_idx, 'R6'] = (H/L)*C
        T.loc[next_idx, 'R5'] = T.loc[next_idx, 'R4'] + 1.168 * (T.loc[next_idx, 'R4'] - T.loc[next_idx, 'R3'])
        
        # Calculate pivot point
        T.loc[next_idx, 'PP'] = (H+L+C) / 3
        
        # Calculate support levels
        T.loc[next_idx, 'S3'] = C - RANGE * 1.1/4
        T.loc[next_idx, 'S4'] = C - RANGE * 1.1/2
        T.loc[next_idx, 'S5'] = T.loc[next_idx, 'S4'] - 1.168 * (T.loc[next_idx, 'S3'] - T.loc[next_idx, 'S4'])
        T.loc[next_idx, 'S6'] = 2*C - T.loc[next_idx, 'R6']
    
    # Handle infinite and NaN values
    T = T.replace([np.inf, -np.inf], np.nan)
    
    # Convert NaN to None for JSON serialization
    for col in T.columns:
        if col != 'Symbol':  # Keep Symbol column as is
            T[col] = T[col].where(pd.notnull(T[col]), None)
    
    return T 