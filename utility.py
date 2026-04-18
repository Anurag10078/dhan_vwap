import logging
import config
logger = logging.getLogger(__name__)
from datetime import datetime
import pandas as pd

def isEntryAllowed():
    currentTime = datetime.now(config.TIME_ZONE).time()
    return currentTime >= getTime(config.START_TIME) and currentTime <= getTime(config.LAST_ENTRY_TIME)

def getTime(timetuple, isdateTime=False):
    if len(timetuple) > 2:
        closingTime = datetime.now(config.TIME_ZONE).replace(hour=timetuple[0], minute=timetuple[1], second=timetuple[2])
    else:
        closingTime = datetime.now(config.TIME_ZONE).replace(hour=timetuple[0], minute=timetuple[1], second=0)
    return closingTime if isdateTime else closingTime.time()


def getTimeCondition():
    return datetime.now(config.TIME_ZONE) < getTime(config.EXIT_TIME,isdateTime=True) and config.RUN_PROCESS

def intializeMasterSym():   # equity
    dhandMasterdf = pd.read_csv('https://images.dhan.co/api-data/api-scrip-master-detailed.csv', low_memory=True)

    #config.MASTER_DF  = dhandMasterdf[(dhandMasterdf.SEGMENT == 'E') & (dhandMasterdf.EXCH_ID == 'NSE' ) & (dhandMasterdf.INSTRUMENT_TYPE == 'ES' )]

    optdf = dhandMasterdf[(dhandMasterdf.SEGMENT == 'D') ]
    optdf['SM_EXPIRY_DATE'] = pd.to_datetime(optdf.SM_EXPIRY_DATE).apply(lambda x: x.date())
    niftydf = optdf[(optdf.SEGMENT == 'D')  & (optdf.INSTRUMENT == 'OPTIDX') & (optdf.UNDERLYING_SYMBOL == config.SYMBOL) & (optdf.SM_EXPIRY_DATE >= datetime.now().date()) ]
    expList = niftydf.SM_EXPIRY_DATE.unique().tolist()
    expList.sort()
    config.EXPIRY_LIST = expList
    config.MASTER_DF = niftydf = niftydf[niftydf.SM_EXPIRY_DATE == expList[0]]

    logger.debug(f'Expiry List  { config.EXPIRY_LIST}')
    logger.debug(f'Symbol Master \n  { config.MASTER_DF}')



