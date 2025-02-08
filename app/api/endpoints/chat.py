from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.api.deps import create_token_auth_router, verify_token

router = create_token_auth_router()

class ChatMessage(BaseModel):
    message: str

# Define your stock level interpretations
STOCK_LEVELS = {
    "R6": {
        "name": "Target 2 LONG",
        "interpretation": "Strong resistance level and second target for long positions. Consider taking full profits.",
        "action": "Consider closing remaining long positions or trailing stop-loss"
    },
    "R5": {
        "name": "Target 1 LONG",
        "interpretation": "First target for long positions. Consider partial profit taking.",
        "action": "Consider taking partial profits on long positions"
    },
    "R4": {
        "name": "Breakout",
        "interpretation": "Key breakout level. Price above suggests bullish momentum.",
        "action": "Watch for bullish continuation patterns"
    },
    "R3": {
        "name": "Sell reversal",
        "interpretation": "Potential reversal zone for short entries.",
        "action": "Look for bearish reversal patterns"
    },
    "PP": {
        "name": "Pivot Point",
        "interpretation": "Key pivot level. Acts as support/resistance.",
        "action": "Monitor price action around this level"
    },
    "S3": {
        "name": "Buy reversal",
        "interpretation": "Potential reversal zone for long entries.",
        "action": "Look for bullish reversal patterns"
    },
    "S4": {
        "name": "Breakdown",
        "interpretation": "Key breakdown level. Price below suggests bearish momentum.",
        "action": "Watch for bearish continuation patterns"
    },
    "S5": {
        "name": "Target 1 SHORT",
        "interpretation": "First target for short positions. Consider partial profit taking.",
        "action": "Consider taking partial profits on short positions"
    },
    "S6": {
        "name": "Target 2 SHORT",
        "interpretation": "Strong support level and second target for short positions. Consider taking full profits.",
        "action": "Consider closing remaining short positions or trailing stop-loss"
    }
}

CLOSING_CONDITIONS = {
    "BULLISH_S3": {
        "condition": "Closing below S3 but above S4",
        "interpretation": "Price is in BULLISH territory",
        "target": "Can move upward towards R3",
        "strategy": "Look for buying opportunities with strict stop-loss below S4"
    },
    "BEARISH_S4": {
        "condition": "Closing below S4 and above S5/S6",
        "interpretation": "Price is in BEARISH territory",
        "target": "Can decline towards S6",
        "strategy": "Look for selling opportunities with stop-loss above R3"
    },
    "BEARISH_R3": {
        "condition": "Closing above R3 but below R4",
        "interpretation": "Price is in BEARISH territory",
        "target": "Can fall back to S3",
        "strategy": "Consider profit booking or short positions with stop-loss above R4"
    },
    "BULLISH_R4": {
        "condition": "Closing above R4 but below R5/R6",
        "interpretation": "Price is in BULLISH territory",
        "target": "Can rise towards R6",
        "strategy": "Hold long positions with trailing stop-loss"
    }
}

def get_closing_analysis(message: str) -> str:
    """Get closing price condition analysis"""
    return """📊 Closing Price Analysis:

1️⃣ BULLISH SCENARIO 1:
   • Condition: Closing below S3 but above S4
   • Interpretation: BULLISH
   • Target: Can move up to R3
   • Strategy: Look for buying opportunities

2️⃣ BEARISH SCENARIO 1:
   • Condition: Closing below S4 (above S5/S6)
   • Interpretation: BEARISH
   • Target: Can fall to S6
   • Strategy: Watch for selling opportunities

3️⃣ BEARISH SCENARIO 2:
   • Condition: Closing above R3 (below R4)
   • Interpretation: BEARISH
   • Target: Can fall to S3
   • Strategy: Consider profit booking/shorts

4️⃣ BULLISH SCENARIO 2:
   • Condition: Closing above R4 (below R5/R6)
   • Interpretation: BULLISH
   • Target: Can rise to R6
   • Strategy: Hold longs with trailing stop-loss"""

def get_level_info(message: str) -> str:
    """Parse user message and return relevant level information"""
    message = message.upper()
    
    # Check for closing price analysis request
    if "CLOSING" in message or "CONDITION" in message or "ANALYSIS" in message:
        return get_closing_analysis(message)
    
    # Check for specific level questions
    for level, info in STOCK_LEVELS.items():
        if level in message:
            return f"""🎯 {level} - {info['name']}
            
📊 Interpretation:
{info['interpretation']}

⚡ Recommended Action:
{info['action']}

💡 Tip: Type 'closing analysis' to see how closing prices relative to levels affect trend interpretation."""
    
    # General questions about levels
    if "LEVELS" in message or "ALL" in message:
        response = """📈 Stock Level Interpretations:

🟢 LONG Targets:
R6 - Target 2 LONG (Final target)
R5 - Target 1 LONG (First target)
R4 - Breakout Level

⚪ Key Levels:
R3 - Sell Reversal Zone
PP - Pivot Point (Key reference)
S3 - Buy Reversal Zone

🔴 SHORT Targets:
S4 - Breakdown Level
S5 - Target 1 SHORT (First target)
S6 - Target 2 SHORT (Final target)

📊 Closing Price Analysis Available!
Type 'closing analysis' to understand how closing prices affect trend interpretation."""
        return response
    
    # Questions about trading direction
    if "LONG" in message or "BUY" in message:
        return """🟢 Long Trading Levels:

1. Entry Zone: Look for entries near S3 (Buy reversal)
2. First Target: R5 level
3. Final Target: R6 level
4. Breakout Level: R4 (Watch for continuation)

Type the level code (e.g., 'R5') for specific details."""

    if "SHORT" in message or "SELL" in message:
        return """🔴 Short Trading Levels:

1. Entry Zone: Look for entries near R3 (Sell reversal)
2. First Target: S5 level
3. Final Target: S6 level
4. Breakdown Level: S4 (Watch for continuation)

Type the level code (e.g., 'S5') for specific details."""
    
    # Default response
    return """Welcome to Stock Level Analysis! 

I can help you understand:
📊 Individual levels (e.g., type 'R6' or 'S3')
📈 All levels (type 'all levels')
🟢 Long trading setup (type 'long')
🔴 Short trading setup (type 'short')
🔍 Closing price analysis (type 'analysis')
🎯 Level interpretations

What would you like to know about?"""

@router.post("/chat")
async def chat(
    message: ChatMessage,
    token: str = Depends(verify_token)
):
    try:
        response = get_level_info(message.message)
        return {"response": response}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Chat failed: {str(e)}"
        ) 