from fastapi import APIRouter, HTTPException, Depends # type: ignore
from typing import Optional
import pandas as pd # type: ignore
from datetime import datetime
from app.api.endpoints.stock_data import get_stock_data
from app.utils.technical_analysis import data_resampling, calculate_levels
from app.api.deps import create_token_auth_router, verify_token

router = create_token_auth_router()

@router.get("/technical/{symbol}")
async def get_technical_analysis(
    symbol: str,
    start_date: str,
    end_date: str,
    period: Optional[str] = "D",
    token: str = Depends(verify_token),
):
    """
    Get technical analysis with support and resistance levels
    
    Args:
        symbol: Stock symbol
        start_date: Start date in DD-MM-YYYY format
        end_date: End date in DD-MM-YYYY format
        period: Resampling period ('D'=Daily, 'W'=Weekly, 'M'=Monthly, 'Q'=Quarterly, 'Y'=Yearly)
    
    Returns:
        JSON with technical analysis data including support and resistance levels
    """
    try:
        # First get the stock data
        stock_data = await get_stock_data(symbol, start_date, end_date)
        
        if not stock_data["data"]:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for symbol {symbol} in the specified date range"
            )
        
        # Convert to DataFrame
        df = pd.DataFrame(stock_data['data'])
        
        # Validate period
        valid_periods = {'D': 'Daily', 'W': 'Weekly', 'M': 'Monthly', 'Q': 'Quarterly', 'Y': 'Yearly'}
        if period not in valid_periods:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period. Must be one of: {', '.join(valid_periods.keys())}"
            )
        
        # Resample data to specified period
        resampled_data = data_resampling(df, period)
        
        # Calculate levels
        analysis_result = calculate_levels(resampled_data)
        
        # Format the result
        analysis_result = analysis_result.reset_index()
        analysis_result['Date'] = analysis_result['Date'].dt.strftime('%Y-%m-%d')
        
        # Convert DataFrame to dict, handling any remaining NaN values
        result_dict = analysis_result.where(pd.notnull(analysis_result), None).to_dict('records')
        
        return {
            "symbol": symbol,
            "period": valid_periods[period],
            "start_date": start_date,
            "end_date": end_date,
            "analysis": result_dict
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Analysis failed: {str(e)}"
        )
