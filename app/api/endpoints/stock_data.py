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
    
    # Sort the DataFrame by date in ascending order
    if isinstance(result.index, pd.DatetimeIndex):
        result = result.sort_index(ascending=True)
        logger.debug("Sorted DataFrame by DatetimeIndex in ascending order")
    elif 'Date' in result.columns:
        result = result.sort_values('Date', ascending=True)
        logger.debug("Sorted DataFrame by Date column in ascending order")
    
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
    
    # Ensure records are sorted by date in ascending order (as a final check)
    records = sorted(records, key=lambda x: x['Date'])
    
    logger.debug(f"Formatted dataframe with {len(records)} records")
    return records

def get_upstox_instrument_key(symbol):
    """
    Map common stock symbols to Upstox instrument keys.
    
    In a production environment, this should be replaced with a proper instrument key lookup 
    against the Upstox API's master contract.
    """
    # Check for index symbols
    index_mapping = {
        "NIFTY 50": "NSE_INDEX|NIFTY 50",
        "NIFTY BANK": "NSE_INDEX|NIFTY BANK",
        "NIFTY": "NSE_INDEX|NIFTY 50",
        "BANKNIFTY": "NSE_INDEX|NIFTY BANK"
    }
    
    if symbol in index_mapping:
        logger.info(f"Using index mapping for {symbol}: {index_mapping[symbol]}")
        return index_mapping[symbol]
    
    # Common mapping for frequently used symbols
    instrument_key_map = {
        "RELIANCE": "NSE_EQ|INE002A01018",
        "TCS": "NSE_EQ|INE467B01029", 
        "INFY": "NSE_EQ|INE009A01021",
        "HDFCBANK": "NSE_EQ|INE040A01034",
        "ICICIBANK": "NSE_EQ|INE090A01021",
        "HINDUNILVR": "NSE_EQ|INE030A01027",
        "SBIN": "NSE_EQ|INE062A01020",
        "BHARTIARTL": "NSE_EQ|INE397D01024",
        "ITC": "NSE_EQ|INE154A01025",
        "KOTAKBANK": "NSE_EQ|INE237A01028",
        "LT": "NSE_EQ|INE018A01030"  # Added LT with its ISIN
    }
    
    # Check if we have a mapping for this symbol
    if symbol in instrument_key_map:
        return instrument_key_map[symbol]
    
    # If the symbol already contains a pipe character, assume it's already in instrument key format
    if '|' in symbol:
        return symbol
    
    # For symbols without a mapping, we'll use a default format with warning
    logger.warning(f"No instrument key mapping for symbol: {symbol}. Using default NSE_EQ format.")
    return f"NSE_EQ|{symbol}"

def fetch_upstox_data(symbol, start_date, end_date, interval='days', interval_value='1'):
    """
    Fetch historical data from Upstox API
    
    Args:
        symbol: Stock symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        interval: Time unit (minutes, hours, days, weeks, months)
        interval_value: Interval value (1, 2, etc. depending on the unit)
    
    Returns:
        DataFrame with historical stock data
    """
    logger.debug(f"Fetching data from Upstox API for {symbol} from {start_date} to {end_date}")
    
    # Get the proper Upstox instrument key for the symbol
    instrument_key = get_upstox_instrument_key(symbol)
    logger.debug(f"Using instrument key: {instrument_key} for symbol: {symbol}")
    
    # Encode the instrument key for URL
    encoded_symbol = urllib.parse.quote(instrument_key)
    
    # Build URL for Upstox API - Note that from_date and to_date are reversed in the URL according to the API docs
    url = f'https://api.upstox.com/v3/historical-candle/{encoded_symbol}/{interval}/{interval_value}/{end_date}/{start_date}'
    
    # For debugging - also try an alternative format without symbol encoding to see if that works
    alt_url = f'https://api.upstox.com/v3/historical-candle/{instrument_key}/{interval}/{interval_value}/{end_date}/{start_date}'
    logger.debug(f"Alternative URL: {alt_url}")
    
    headers = {
        'Accept': 'application/json'
    }
    
    logger.debug(f"Making request to Upstox API: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        
        # Log response details for debugging
        logger.debug(f"Upstox API response status code: {response.status_code}")
        if response.status_code != 200:
            logger.debug(f"Response content: {response.text[:500]}")  # Log first 500 chars to avoid huge logs
            
            # If first attempt fails with 400, try alternative URL format
            if response.status_code == 400 and "Invalid Instrument key" in response.text:
                logger.debug("Trying alternative URL format without encoding pipe character")
                try:
                    alt_response = requests.get(alt_url, headers=headers)
                    if alt_response.status_code == 200:
                        logger.debug("Alternative URL format successful")
                        response = alt_response
                    else:
                        logger.debug(f"Alternative URL also failed: {alt_response.status_code}")
                except Exception as alt_e:
                    logger.debug(f"Alternative URL request failed: {str(alt_e)}")
        
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        data = response.json()
        logger.debug(f"Upstox API response received: {data['status']}")
        
        if data['status'] != 'success' or 'data' not in data or 'candles' not in data['data'] or not data['data']['candles']:
            logger.warning(f"No data found in Upstox API response for {symbol}")
            return pd.DataFrame()
        
        # Convert candles data to DataFrame
        candles = data['data']['candles']
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Set timestamp as index
        df.set_index('timestamp', inplace=True)
        
        # Convert numeric columns to float
        for col in ['open', 'high', 'low', 'close', 'volume', 'oi']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Rename columns to match expected format
        df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'oi': 'OpenInterest'
        }, inplace=True)
        
        logger.debug(f"DataFrame created with {len(df)} records")
        return df
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from Upstox API: {str(e)}", exc_info=True)
        # Try to get more information about the error
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response text: {e.response.text[:1000]}")  # Log first 1000 chars
        raise e
    except ValueError as e:
        logger.error(f"Error parsing Upstox API response: {str(e)}", exc_info=True)
        raise e

@router.get("/stock/{symbol}")
async def get_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    period: Optional[str] = None,
    isin: Optional[str] = None,
    is_index: Optional[bool] = False,
    token: str = Depends(verify_token),
):
    """
    Fetch historical stock data for a given symbol and date range.
    
    Args:
        symbol: Stock symbol
        start_date: Start date in DD-MM-YYYY format
        end_date: End date in DD-MM-YYYY format
        period: Optional - Resampling period ('D', 'W', 'M', 'Q', 'Y')
        isin: Optional - ISIN of the stock
        is_index: Optional - Whether the symbol is an index (Nifty 50, Bank Nifty, etc.)
    """
    logger.info(f"Stock data request for symbol: {symbol}, start_date: {start_date}, end_date: {end_date}, is_index: {is_index}")
    
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
        # Convert dates to Upstox format (YYYY-MM-DD)
        upstox_start_date = start.strftime("%Y-%m-%d")
        upstox_end_date = end.strftime("%Y-%m-%d")
        
        # Map period to Upstox intervals if provided
        interval = 'days'  # Default to daily data
        interval_value = '1'
        
        if period:
            # Map period to Upstox timeframes
            period_mapping = {
                'D': ('days', '1'),
                'W': ('weeks', '1'),
                'M': ('months', '1'),
                'H': ('hours', '1'),
                '15M': ('minutes', '15'),
                '30M': ('minutes', '30'),
                '5M': ('minutes', '5')
            }
            
            if period in period_mapping:
                interval, interval_value = period_mapping[period]
                logger.debug(f"Mapped period {period} to Upstox interval {interval}/{interval_value}")
            else:
                logger.warning(f"Unsupported period {period}, defaulting to daily data")
        
        logger.debug(f"Fetching historical data for {symbol} from {upstox_start_date} to {upstox_end_date} with interval {interval}/{interval_value}")
        
        # Fetch historical data from Upstox
        try:
            # If it's an index, use the index format
            if is_index:
                logger.info(f"Using index format for {symbol}")
                symbol = f"NSE_INDEX|{symbol}"
            # If ISIN is provided, create an instrument key with it
            elif isin:
                # Override the symbol with a proper instrument key including ISIN
                logger.info(f"Using ISIN {isin} for symbol {symbol}")
                symbol = f"NSE_EQ|{isin}"
                
            result = fetch_upstox_data(
                symbol=symbol,
                start_date=upstox_start_date,
                end_date=upstox_end_date,
                interval=interval,
                interval_value=interval_value
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
            logger.error(f"Error fetching data from Upstox API: {str(e)}", exc_info=True)
            # Log the error details for debugging
            logger.error(f"Params: symbol={symbol}, start={upstox_start_date}, end={upstox_end_date}, interval={interval}/{interval_value}")
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
