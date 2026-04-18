from zoneinfo import ZoneInfo
TIME_ZONE = ZoneInfo("Asia/Kolkata")
import datetime
from datetime import  datetime , timedelta

EXPIRY_LIST = []
MASTER_DF = None

RUN_PROCESS  =True 
POSITION_CONFIG = {}
POSITION_CONFIG_CE = {}
POSITION_CONFIG_PE = {}
CLIENT_ID = ''
PIN =      ''
TOTP_TOKEN = ''


SYM_MAP = {'NIFTY':(13,50), 'BANKNIFTY':(25,100) }   # (ID, strike gap)
STRIKE_OFFSET = 11
SYMBOL = 'NIFTY'
EXCNAHGE= 'NSE_FNO'
PRODUCT_TYPE = 'INTRADAY'
WIV_STRIKE_RANGE=5
WIV = None
IDX_ATR_PERIOD =5
IDX_ATR_PERIOD2 =6
ATR_MULTIPLIER = 1.5
TIMEFRAME = 15 # in minutes
MULTIPLIER = 1
RR = 3
IS_OPEN_POSITION = False
TILL_OTM=15

SquareOffTime = (15,20,0)
EXIT_TIME = (23,55,0)
START_TIME = (17,22,0)
LAST_ENTRY_TIME = (14,30,0)
# dhanObj=Dhan
# CANDLEDF=dhanObj.get_intraday_candles(security_id=SYM_MAP[SYMBOL][0],
#                                                 exchange_segment='IDX_I', instrument_type='EQUITY',from_dt = datetime.now(TIME_ZONE),timeFrame=TIMEFRAME,skipIncomplete=True)
