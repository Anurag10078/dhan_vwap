from zoneinfo import ZoneInfo
TIME_ZONE = ZoneInfo("Asia/Kolkata")

EXPIRY_LIST = []
MASTER_DF = None

RUN_PROCESS  =True 
POSITION_CONFIG = {}
CLIENT_ID = '1100089959'
PIN =      ''
TOTP_TOKEN = ''

SYM_MAP = {'NIFTY':(13,50), 'BANKNIFTY':(25,100) }   # (ID, strike gap)
STRIKE_OFFSET = 25
SYMBOL = 'NIFTY'
EXCNAHGE= 'NSE_FNO'
PRODUCT_TYPE = 'INTRADAY'
WIV_STRIKE_RANGE=5
WIV = None
IDX_ATR_PERIOD =5
IDX_ATR_PERIOD2 =6
ATR_MULTIPLIER = 1.5
TIMEFRAME = 1 # in minutes
MULTIPLIER = 1
RR = 3
IS_OPEN_POSITION = False


# https://api.telegram.org/bot<yor_token>/getUpdates


BOT_TOKEN = ''
BOT_CHAT_ID = ''  # sender
SquareOffTime = (15,20,0)
EXIT_TIME = (15,30,0)
START_TIME = (9,30,0)
LAST_ENTRY_TIME = (14,30,0)


#  /root/dft/dhanenv/bin/python

# 15 9 * * 1-5 /root/dft/dhanenv/bin/python /root/dft/demo.py >> /root/dft/demo.log 