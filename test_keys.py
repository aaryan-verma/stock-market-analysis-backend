import sys
sys.path.append('.')
from app.api.endpoints.stock_data import get_upstox_instrument_key
print('Default format:', get_upstox_instrument_key('LT'))
print('With ISIN format:', get_upstox_instrument_key('NSE_EQ|INE018A01030'))
