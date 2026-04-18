import utility
from brokerClass import DhanAPICleint
import config
def main():    
    utility.intializeMasterSym()
    # dhanObj= DhanAPICleint()
    # list=[40770, 40772, 40774, 40776, 40778, 40781, 40783, 40785, 40788, 40790, 40792]
    # ltp=dhanObj.get_ticker_response(instrument=list)
    # print(ltp)
    # spot_ltp=dhanObj.getLtp(security_id=config.SYM_MAP['NIFTY'][0],exchange='IDX_I')
    # print(spot_ltp)
    
    print(config.MASTER_DF.STRIKE_PRICE)
if __name__ == "__main__":
    main()