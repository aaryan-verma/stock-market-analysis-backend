from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import pandas as pd
from datetime import datetime, timedelta
import requests
import json
import urllib.parse
import concurrent.futures
from concurrent.futures import ALL_COMPLETED
import time
from app.api.deps import create_token_auth_router, verify_token
from app.api.logger import get_logger
from openchart import NSEData

# Set up logger for this module
logger = get_logger(__name__)

router = create_token_auth_router()

def format_dataframe_result(result, symbol):
    """
    Format the dataframe result to match the original response format
    """
    logger.debug("Formatting dataframe result")
    if result.empty:
        return []
    
    # Print the full dataframe for debugging
    logger.debug(f"Raw result columns: {result.columns.tolist()}")
    logger.debug(f"Raw result shape: {result.shape}")
    logger.debug(f"Raw result first row: {result.iloc[0].to_dict() if len(result) > 0 else 'Empty'}")
    
    # Rename OpenChart columns to match our expected format
    columns_map = {
        'timestamp': 'Date',
        'date': 'Date',  # Add this alternative
        'datetime': 'Date',  # Add this alternative
        'time': 'Date',  # Add this alternative
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close'
    }
    
    # Rename columns that exist in the DataFrame
    rename_cols = {k: v for k, v in columns_map.items() if k in result.columns}
    logger.debug(f"Columns being renamed: {rename_cols}")
    result = result.rename(columns=rename_cols)
    
    logger.debug(f"Columns after renaming: {result.columns.tolist()}")
    
    # Add Symbol column with the requested symbol
    result['Symbol'] = symbol
    
    # If we don't have a Date column, check if we need to generate it from index
    if 'Date' not in result.columns and isinstance(result.index, pd.DatetimeIndex):
        logger.debug("Using DatetimeIndex as Date column")
        result['Date'] = result.index
    
    # Ensure required columns exist
    required_columns = ['Date', 'Symbol', 'High', 'Low', 'Open', 'Close']
    for col in required_columns:
        if col not in result.columns:
            logger.debug(f"Column {col} not found, setting to None")
            result[col] = None
    
    # Debug the date column if it exists
    if 'Date' in result.columns:
        logger.debug(f"Date column type: {type(result['Date'])}")
        logger.debug(f"Date column dtype: {result['Date'].dtype}")
        if len(result) > 0:
            logger.debug(f"Sample date value: {result['Date'].iloc[0]}, type: {type(result['Date'].iloc[0])}")
    
    # Check if the index contains date information
    logger.debug(f"Index type: {type(result.index)}")
    if isinstance(result.index, pd.DatetimeIndex):
        logger.debug(f"Index is DatetimeIndex, first value: {result.index[0] if len(result.index) > 0 else 'Empty'}")
    elif len(result.index) > 0:
        logger.debug(f"First index value: {result.index[0]}, type: {type(result.index[0])}")
    
    # Convert the dataframe to records directly
    records = []
    for idx, row in result.iterrows():
        record = {}
        
        # Try to get the date from different sources
        date_value = None
        
        # Try 1: Check if Date column exists and has value
        if 'Date' in row and row['Date'] is not None:
            date_value = row['Date']
            logger.debug(f"Using Date column value: {date_value}")
        
        # Try 2: Check if index is a datetime
        elif isinstance(idx, (pd.Timestamp, datetime)):
            date_value = idx
            logger.debug(f"Using index as date: {date_value}")
        
        # Try 3: Check other possible date columns
        for date_col in ['date', 'timestamp', 'datetime', 'time']:
            if date_col in row and row[date_col] is not None and date_value is None:
                date_value = row[date_col]
                logger.debug(f"Using {date_col} column value: {date_value}")
                break
        
        # Format the date if we found a value
        if date_value is not None:
            if isinstance(date_value, (pd.Timestamp, datetime)):
                record['Date'] = date_value.strftime('%Y-%m-%d')
            elif isinstance(date_value, str):
                # If it's already a string, try to parse it
                try:
                    parsed_date = pd.to_datetime(date_value)
                    record['Date'] = parsed_date.strftime('%Y-%m-%d')
                except:
                    # If parsing fails, use the string directly
                    record['Date'] = date_value
            else:
                # For any other type, convert to string
                record['Date'] = str(date_value)
        else:
            # If no date was found, use the current date as a fallback
            record['Date'] = datetime.now().strftime('%Y-%m-%d')
            logger.debug("No date found, using current date")
        
        # Add the rest of the columns
        for col in required_columns:
            if col != 'Date':
                record[col] = row.get(col)
        
        records.append(record)
    
    logger.debug(f"Formatted dataframe with {len(records)} records")
    return records

@router.get("/stock/{symbol}")
async def get_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    period: Optional[str] = None,
    token: str = Depends(verify_token),
):
    """
    Fetch historical stock data for a given symbol and date range.
    
    Args:
        symbol: Stock symbol
        start_date: Start date in DD-MM-YYYY format
        end_date: End date in DD-MM-YYYY format
        period: Optional - Resampling period ('D', 'W', 'M', 'Q', 'Y')
    
    Returns:
        JSON with historical stock data
    """
    logger.info(f"Stock data request for symbol: {symbol}, start_date: {start_date}, end_date: {end_date}")
    
    try:
        # Validate dates
        start = datetime.strptime(start_date, "%d-%m-%Y")
        end = datetime.strptime(end_date, "%d-%m-%Y")
    except ValueError as e:
        logger.warning(f"Invalid date format: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Please use DD-MM-YYYY format"
        )

    try:
        # Initialize the NSEData class
        nse = NSEData()
        
        # Download master data - this is required before fetching historical data
        logger.debug("Downloading master data from NSE")
        nse.download()
        
        # Map period to OpenChart intervals if provided
        interval = '1d'  # Default to daily data
        if period:
            # Map period to OpenChart timeframes
            period_mapping = {
                'D': '1d',
                'W': '1w',
                'M': '1M',
                'H': '1h',
                '15M': '15m',
                '30M': '30m',
                '5M': '5m'
            }
            interval = period_mapping.get(period, '1d')
        
        logger.debug(f"Fetching historical data for {symbol} from {start_date} to {end_date} with interval {interval}")
        
        # Fetch historical data
        try:
            result = nse.historical(
                symbol=symbol,
                exchange='NSE',
                start=start,
                end=end,
                interval=interval
            )
            
            # Debug logs for understanding the structure of the data
            logger.debug(f"Result type: {type(result)}")
            logger.debug(f"Column dtypes: {result.dtypes}")
            logger.debug(f"Index type: {type(result.index)}")
            
            if not result.empty:
                logger.debug(f"Sample row: {result.iloc[0].to_dict()}")
                logger.debug(f"All columns: {result.columns.tolist()}")
                if isinstance(result.index, pd.DatetimeIndex):
                    logger.debug(f"Index is a DatetimeIndex, first value: {result.index[0]}")
                else:
                    logger.debug(f"Index is not a DatetimeIndex: {type(result.index)}")
                    
                # Try to inspect the raw dataframe structure
                logger.debug(f"Raw result head:\n{result.head().to_string()}")
            
        except Exception as e:
            logger.error(f"Error fetching data from OpenChart: {str(e)}", exc_info=True)
            # Log the error details for debugging
            logger.error(f"Params: symbol={symbol}, start={start}, end={end}, interval={interval}")
            raise HTTPException(
                status_code=503,
                detail=f"Error fetching data: {str(e)}"
            )
        
        if result.empty:
            logger.warning(f"No data found for symbol {symbol} in the specified date range")
            raise HTTPException(
                status_code=404,
                detail=f"No data found for symbol {symbol} in the specified date range"
            )
        
        logger.info(f"Successfully retrieved {len(result)} records for {symbol}")
        
        # Format the result to match the original API response
        formatted_data = format_dataframe_result(result, symbol)
        
        return {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "data": formatted_data
        }
        
    except Exception as e:
        logger.error(f"Error processing stock data request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"An error occurred: {str(e)}"
        )
