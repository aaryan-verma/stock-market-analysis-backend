from fastapi import APIRouter, HTTPException
from typing import List, Dict
from datetime import datetime, timedelta
import aiohttp
from app.api.logger import get_logger

# Set up logger for this module
logger = get_logger(__name__)

router = APIRouter()

async def fetch_news(symbol: str, max_items: int = 10) -> List[Dict]:
    """Fetch stock-specific news using NewsAPI.org"""
    logger.debug(f"Fetching news for symbol: {symbol}, max_items: {max_items}")
    # Free API key from NewsAPI.org
    API_KEY = "d6576629c1114f1ca23237a17ad35a2b"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Get date range (last 30 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            # Format dates
            from_date = start_date.strftime('%Y-%m-%d')
            
            # Clean up symbol and create search query
            clean_symbol = symbol.replace('.NSE', '').replace('.NS', '')
            # Add company name variations for better results
            company_names = {
                'RELIANCE': 'Reliance Industries',
                'TCS': 'Tata Consultancy Services',
                'INFY': 'Infosys',
                'HDFCBANK': 'HDFC Bank',
                # Add more mappings as needed
            }
            
            search_query = company_names.get(clean_symbol, clean_symbol)
            search_query = f"{search_query} stock market OR finance OR trading"
            
            logger.debug(f"Using search query: {search_query}")
            
            # Build URL for NewsAPI
            url = (
                "https://newsapi.org/v2/everything"
                f"?q={search_query}"
                f"&from={from_date}"
                "&language=en"
                "&sortBy=relevancy"
                f"&pageSize={max_items}"
                f"&apiKey={API_KEY}"
            )
            
            logger.debug(f"Making request to NewsAPI")
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"NewsAPI returned status code: {response.status}")
                    raise HTTPException(
                        status_code=response.status,
                        detail="Failed to fetch news from external API"
                    )
                
                data = await response.json()
                articles = data.get('articles', [])
                logger.debug(f"Retrieved {len(articles)} articles from NewsAPI")
                
                # Process and sort news by relevance/impact
                processed_news = []
                for item in articles:
                    try:
                        # Calculate impact score
                        impact_score = 0
                        
                        # Factor 1: Source reliability
                        reliable_sources = ['Reuters', 'Bloomberg', 'CNBC', 'Financial Times', 
                                         'Economic Times', 'Moneycontrol', 'Business Standard']
                        if any(source.lower() in item.get('source', {}).get('name', '').lower() 
                              for source in reliable_sources):
                            impact_score += 2
                        
                        # Factor 2: Title relevance
                        title = item.get('title', '').lower()
                        company_name = clean_symbol.lower()
                        if company_name in title:
                            impact_score += 3
                            
                        # Factor 3: Content keywords
                        description = item.get('description', '').lower()
                        important_keywords = ['earnings', 'profit', 'revenue', 'guidance', 
                                           'acquisition', 'merger', 'quarterly', 'results']
                        impact_score += sum(1 for word in important_keywords 
                                         if word in title or word in description)
                        
                        # Determine impact level
                        if impact_score >= 4:
                            impact = "high"
                        elif impact_score >= 2:
                            impact = "medium"
                        else:
                            impact = "low"
                        
                        # Process sentiment
                        positive_words = ['surge', 'jump', 'rise', 'gain', 'up', 'high', 'growth', 'profit']
                        negative_words = ['fall', 'drop', 'decline', 'down', 'low', 'loss', 'crash', 'risk']
                        
                        if any(word in title for word in positive_words):
                            sentiment = "positive"
                        elif any(word in title for word in negative_words):
                            sentiment = "negative"
                        else:
                            sentiment = "neutral"
                        
                        # Format date
                        pub_date = datetime.strptime(item['publishedAt'][:10], '%Y-%m-%d')
                        formatted_date = pub_date.strftime("%Y-%m-%d")
                        
                        # Only include relevant news
                        if impact_score >= 2:
                            processed_news.append({
                                "date": formatted_date,
                                "headline": item.get('title', ''),
                                "summary": item.get('description', ''),
                                "sentiment": sentiment,
                                "impact": impact,
                                "impact_score": impact_score,
                                "url": item.get('url', ''),
                                "source": item.get('source', {}).get('name', ''),
                                "image_url": item.get('urlToImage', '')
                            })
                            logger.debug(f"Added news item with impact: {impact}, score: {impact_score}")
                        
                    except Exception as e:
                        logger.error(f"Error processing news item: {str(e)}", exc_info=True)
                        continue
                
                # Sort by impact score and get top 5
                sorted_news = sorted(
                    processed_news, 
                    key=lambda x: (x.pop('impact_score', 0), x['date']), 
                    reverse=True
                )[:5]
                
                logger.info(f"Successfully processed news for {symbol}, returning {len(sorted_news)} items")
                return sorted_news
                
    except Exception as e:
        logger.error(f"News API error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch news: {str(e)}"
        )

@router.get("/{symbol}")
async def get_stock_news(symbol: str):
    """Get top 5 most impactful news items for a stock"""
    logger.info(f"News request for symbol: {symbol}")
    try:
        # Limit news items processed
        news_items = await fetch_news(symbol, max_items=10)  # Process fewer items
        logger.debug(f"Returning {len(news_items)} news items for {symbol}")
        return {"news": news_items[:5]}  # Return only top 5
    except Exception as e:
        logger.error(f"Error in get_stock_news: {str(e)}", exc_info=True)
        raise HTTPException(status_code=503, detail=str(e)) 