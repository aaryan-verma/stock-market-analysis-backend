import requests
import pandas as pd
import datetime
import urllib.parse
import time

def get_upstox_instrument_key(symbol):
    """
    Map common stock symbols to Upstox instrument keys.
    """
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
        "KOTAKBANK": "NSE_EQ|INE237A01028"
    }
    
    # Check if we have a mapping for this symbol
    if symbol in instrument_key_map:
        return instrument_key_map[symbol]
    
    # If the symbol already contains a pipe character, assume it's already in instrument key format
    if '|' in symbol:
        return symbol
    
    # For symbols without a mapping, we'll use a default format with warning
    print(f"No instrument key mapping for symbol: {symbol}. Using default NSE_EQ format.")
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
    print(f"Fetching data from Upstox API for {symbol} from {start_date} to {end_date}")
    
    # Get the proper Upstox instrument key for the symbol
    instrument_key = get_upstox_instrument_key(symbol)
    print(f"Using instrument key: {instrument_key} for symbol: {symbol}")
    
    # Encode the instrument key for URL
    encoded_symbol = urllib.parse.quote(instrument_key)
    
    # Build URL for Upstox API - Note that from_date and to_date are reversed in the URL according to the API docs
    url = f'https://api.upstox.com/v3/historical-candle/{encoded_symbol}/{interval}/{interval_value}/{end_date}/{start_date}'
    
    # For debugging - also try an alternative format without symbol encoding to see if that works
    alt_url = f'https://api.upstox.com/v3/historical-candle/{instrument_key}/{interval}/{interval_value}/{end_date}/{start_date}'
    print(f"Alternative URL: {alt_url}")
    
    headers = {
        'Accept': 'application/json'
    }
    
    print(f"Making request to Upstox API: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        
        # Print response details for debugging
        print(f"Upstox API response status code: {response.status_code}")
        if response.status_code != 200:
            print(f"Response content: {response.text[:500]}")  # Print first 500 chars
            
            # If first attempt fails with 400, try alternative URL format
            if response.status_code == 400 and "Invalid Instrument key" in response.text:
                print("Trying alternative URL format without encoding pipe character")
                try:
                    alt_response = requests.get(alt_url, headers=headers)
                    if alt_response.status_code == 200:
                        print("Alternative URL format successful")
                        response = alt_response
                    else:
                        print(f"Alternative URL also failed: {alt_response.status_code}")
                except Exception as alt_e:
                    print(f"Alternative URL request failed: {str(alt_e)}")
        
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        data = response.json()
        print(f"Upstox API response received: {data['status']}")
        
        if data['status'] != 'success' or 'data' not in data or 'candles' not in data['data'] or not data['data']['candles']:
            print(f"No data found in Upstox API response for {symbol}")
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
        
        print(f"DataFrame created with {len(df)} records")
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Upstox API: {str(e)}")
        # Try to get more information about the error
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response text: {e.response.text[:1000]}")  # Print first 1000 chars
        raise e
    except ValueError as e:
        print(f"Error parsing Upstox API response: {str(e)}")
        raise e

# Define test dates (use current date and 30 days back to ensure we have data)
current_date = datetime.datetime.now()
end_date = current_date.strftime("%Y-%m-%d")
start_date = (current_date - datetime.timedelta(days=30)).strftime("%Y-%m-%d")

# Test symbols with both formats and mapped symbols
symbols_to_test = [
    "RELIANCE",  # Should use the mapped instrument key
    "TCS",       # Should use the mapped instrument key
    "NSE_EQ|INE848E01016"  # Already in Upstox format
]

for symbol in symbols_to_test:
    print(f"\n\nTesting symbol: {symbol}")
    print("=" * 60)
    
    # Fetch daily historical data
    try:
        data = fetch_upstox_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval='days',
            interval_value='1'
        )
        
        # Display the fetched data
        if not data.empty:
            print("Daily historical data (Last 30 days):")
            print(data.head())
            print(f"Total records: {len(data)}")
        else:
            print("No data available for the specified symbol and time period.")
            
    except Exception as e:
        print(f"Error testing daily data for {symbol}: {str(e)}")
    
    # Pause between requests to avoid rate limiting
    time.sleep(2)
    
    # Try another interval - weekly data
    try:
        weekly_data = fetch_upstox_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval='weeks',
            interval_value='1'
        )
        
        if not weekly_data.empty:
            print("Weekly historical data:")
            print(weekly_data)
        else:
            print("No weekly data available for the specified symbol and time period.")
    except Exception as e:
        print(f"Error testing weekly data for {symbol}: {str(e)}")
    
    # Pause between symbols
    time.sleep(2) 