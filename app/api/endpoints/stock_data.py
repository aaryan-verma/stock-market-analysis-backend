from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import pandas as pd
from datetime import datetime
import requests
import json
import urllib.parse
import concurrent.futures
from concurrent.futures import ALL_COMPLETED
import time
from app.api.deps import create_token_auth_router, verify_token

router = create_token_auth_router()

HISTORICAL_DATA_URL = 'https://www.nseindia.com/api/historical/cm/equity?series=[%22EQ%22]&'
BASE_URL = 'https://www.nseindia.com/'

def get_adjusted_headers():
    return {
        'Host': 'www.nseindia.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
    }

def fetch_cookies():
    try:
        response = requests.get(BASE_URL, timeout=30, headers=get_adjusted_headers())
        response.raise_for_status()
        time.sleep(1)  # Add a small delay
        return response.cookies.get_dict()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch cookies: {str(e)}")

def fetch_url(url, cookies):
    try:
        headers = get_adjusted_headers()
        # Add accept-encoding header to handle gzip
        headers['Accept-Encoding'] = 'gzip, deflate'
        
        response = requests.get(url, timeout=30, headers=headers, cookies=cookies)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        if response.status_code == requests.codes.ok:
            # Check if the content is empty
            if not response.content:
                raise HTTPException(status_code=503, detail="Empty response received from server")
                
            try:
                json_response = response.json()  # Use response.json() instead of json.loads()
                if 'data' not in json_response:
                    raise HTTPException(status_code=503, detail="Invalid data format received from server")
                return pd.DataFrame.from_dict(json_response['data'])
            except ValueError as e:
                raise HTTPException(status_code=503, detail=f"Invalid JSON response: {str(e)}")
        else:
            raise HTTPException(status_code=503, detail=f"Server returned status code: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Request failed: {str(e)}")

def format_dataframe_result(result):
    columns_required = ["CH_TIMESTAMP", "CH_SYMBOL", "CH_TRADE_HIGH_PRICE",
                       "CH_TRADE_LOW_PRICE", "CH_OPENING_PRICE", "CH_CLOSING_PRICE"]
    result = result[columns_required]
    result = result.set_axis(
        ['Date', 'Symbol', 'High', 'Low', 'Open', 'Close'], axis=1)
    result['Date'] = pd.to_datetime(result['Date'])
    result = result.sort_values('Date', ascending=True)
    result.reset_index(drop=True, inplace=True)
    return result.to_dict('records')

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
    try:
        # Validate dates
        datetime.strptime(start_date, "%d-%m-%Y")
        datetime.strptime(end_date, "%d-%m-%Y")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Please use DD-MM-YYYY format"
        )

    try:
        cookies = fetch_cookies()
        
        start = datetime.strptime(start_date, "%d-%m-%Y")
        end = datetime.strptime(end_date, "%d-%m-%Y")
        
        url_list = []
        window_size = pd.Timedelta(days=30)  # Reduced window size
        
        current_window_start = start
        while current_window_start < end:
            current_window_end = min(current_window_start + window_size, end)
            
            st = current_window_start.strftime('%d-%m-%Y')
            et = current_window_end.strftime('%d-%m-%Y')
            
            params = {
                'symbol': symbol,
                'from': st,
                'to': et
            }
            url = HISTORICAL_DATA_URL + urllib.parse.urlencode(params)
            url_list.append(url)
            
            current_window_start = current_window_end + pd.Timedelta(days=1)

        result = pd.DataFrame()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:  # Reduced max_workers
            future_to_url = {executor.submit(fetch_url, url, cookies): url for url in url_list}
            
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    df = future.result()
                    if not df.empty:
                        result = pd.concat([result, df])
                    time.sleep(0.5)  # Add delay between requests
                except Exception as exc:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Error fetching data: {str(exc)}"
                    )

        if result.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for symbol {symbol} in the specified date range"
            )

        return {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "data": format_dataframe_result(result)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"An error occurred: {str(e)}"
        )
