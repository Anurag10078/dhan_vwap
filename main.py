import config as config
from logging import getLogger
from logger import setup_logging   
from datetime import datetime,  time as tt , timedelta
import utility as utility
setup_logging()
logger = getLogger(__name__)
from time import sleep
import threading
import pandas_ta as ta
from typing import TYPE_CHECKING
from dhanhq import MarketFeed
from brokerClass import  DhanAPICleint

if TYPE_CHECKING:
    from brokerClass import DhanAPICleint

def secTowaitFinishCandle():
    tf = config.TIMEFRAME
    currenttime =datetime.now(config.TIME_ZONE)
    minutes = (currenttime - timedelta(minutes=15)).minute
    remaintime = minutes%tf  
    interval = (tf -remaintime)*60 - currenttime.second
    return interval
def getcondition(dhanObj: 'DhanAPICleint'):
    from_date= datetime.now(config.TIME_ZONE) - timedelta(days=4)
    candledf = dhanObj.get_intraday_candles(security_id=config.SYM_MAP[config.SYMBOL][0],
                                                exchange_segment='IDX_I', instrument_type='EQUITY',from_dt = from_date,timeFrame= config.TIMEFRAME,skipIncomplete=True)
    candledf.set_index('timestamp', inplace=True, drop=True)
    candledf['vwap']=ta.vwap(high  = candledf.high, low=candledf.low, close = candledf.close, volume = candledf.volume)
    candledf.reset_index(inplace=True)
    candledf['vwap'] = candledf['vwap']
    candledf=candledf.dropna()
    logger.info(f'Got candle data for condition check {candledf.tail()}')
    lastrow = candledf.iloc[-1]
    diff = lastrow.close - lastrow.vwap
    diff=diff
    if ( diff<-60 and diff>-75) or diff>110:
        condition='sell'
        logger.info(f'Condition is {condition}')
        return orderforcond1(dhanObj,condition)
    elif (diff>60 and diff<75) or diff<-110:
        condition='buy'
        logger.info(f'Condition is {condition}')
        return orderforcond1(dhanObj,condition)
    elif (diff>=-50 and diff<0)or (diff<=50 and diff>0):
        condition='neutral'
        logger.info(f'Condition is {condition}')
        return orderforcond2(dhanObj,condition)
    else:
        return 'notrade'

def orderforcond1(dhanObj: 'DhanAPICleint', condition: str):
    symdf = config.MASTER_DF
    strikeGap = config.SYM_MAP[config.SYMBOL][1]
    spotID = config.SYM_MAP[config.SYMBOL][0]
    ce_open=False
    openposition=False
    while utility.getTimeCondition():
        try:
            if condition == 'sell'  and not openposition and condition != 'notrade':
                    from_date= datetime.now(config.TIME_ZONE) - timedelta(days=4)
                    logger.info('Placing sell order for CE ')
                    candledf = dhanObj.get_intraday_candles(security_id=config.SYM_MAP[config.SYMBOL][0],
                                                exchange_segment='IDX_I', instrument_type='EQUITY',from_dt = from_date,timeFrame= config.TIMEFRAME,skipIncomplete=True)
                    lastcandle = candledf.iloc[-1]
                    strike=int(lastcandle.close/strikeGap)*strikeGap
                    ceStrike = strike + config.STRIKE_OFFSET*strikeGap
                    openposition=True
                    #sell ce at ce strike
                    symInfo = symdf[(symdf['STRIKE_PRICE'] == ceStrike) & (symdf['OPTION_TYPE'] == 'CE')].iloc[0]
                    security_id = symInfo['SECURITY_ID']
                    logger.info(f'Placing sell order for CE {symInfo["SYMBOL_NAME"]} at strike {ceStrike}')
                    #placing order for CE
                    #security_id = symInfo['SECURITY_ID']
                    qty = config.MULTIPLIER*int(symInfo['LOT_SIZE'])
                    limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'BUY')
                    orderid = dhanObj.placeOrder(security_id=str(security_id), transType='BUY', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType = config.PRODUCT_TYPE, limitPrice=limitPrice, triggerPrice=0)
                    ceopen=True
                    logger.info(f'Placed sell order for CE {symInfo["SYMBOL_NAME"]} with order id {orderid}')
                    for i in range(10):
                        orderInfo = dhanObj.getOrderStatus(orderid)
                        logger.info(f'Order Status {orderInfo}')
                        if orderInfo['orderStatus'] == 'TRADED':
                            orderInfo = dhanObj.getOrderByID(orderid)
                            avgPrice = orderInfo['averageTradedPrice']
                            sl=avgPrice + (avgPrice*(20/100))
                            risk = sl - avgPrice
                            target=avgPrice - risk*config.RR
                            logger.info(f'Order Executed at price {avgPrice}')
                            config.POSITION_CONFIG = {'tsym': symInfo['SYMBOL_NAME'], 'security_id': orderInfo['securityId'], 'qty': qty, 
                                                'avgPrice': avgPrice,'SL': sl,'target': target}
                            logger.info(f'Position Config {config.POSITION_CONFIG}')
                            break
                        else:
                            logger.info(f'Order not executed yet, modify with new limit price')
                            limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'BUY')
                                    # modify order with new limit price
                                    #(orderid=orderid, limitPrice=limitPrice)
                        sleep(1)
                    
            elif condition == 'buy'  and not openposition and condition != 'notrade' and ce_open==False:
                    from_date= datetime.now(config.TIME_ZONE) - timedelta(days=4)
                    logger.info('Placing sell order for PE i.e. upside view ')
                    candledf = dhanObj.get_intraday_candles(security_id=config.SYM_MAP[config.SYMBOL][0],
                                                exchange_segment='IDX_I', instrument_type='EQUITY',from_dt = from_date,timeFrame= config.TIMEFRAME,skipIncomplete=True)
                    lastcandle = candledf.iloc[-1]
                    strike=int(lastcandle.close/strikeGap)*strikeGap
                    peStrike = strike - config.STRIKE_OFFSET*strikeGap
                    
                    #sell pe at pe strike
                    symInfo = symdf[(symdf['STRIKE_PRICE'] == peStrike) & (symdf['OPTION_TYPE'] == 'PE')].iloc[0]
                    security_id = symInfo['SECURITY_ID']
                    logger.info(f'Placing sell order for PE {symInfo["SYMBOL_NAME"]} at strike {peStrike}')
                    #dhanObj.subscribe_symbols([(MarketFeed.NSE_FNO, "62609", MarketFeed.Ticker)])
                    #placing order for PE
                    #security_id = symInfo['SECURITY_ID']
                    qty = config.MULTIPLIER*int(symInfo['LOT_SIZE'])
                    limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'SELL')
                    orderid = dhanObj.placeOrder(security_id=str(security_id), transType='SELL', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=limitPrice, triggerPrice=0)
                    
                    logger.info(f'Placed sell order for PE {symInfo["SYMBOL_NAME"]} with order id {orderid}')
                    
                    openposition=True                    
                    dhanObj.subscribe_symbols([(MarketFeed.NSE_FNO,str(security_id), MarketFeed.Ticker)])
                    
                    #check order is exexuted or not
                    for i in range(10):
                        orderInfo = dhanObj.getOrderStatus(orderid)
                        logger.info(f'Order Status {orderInfo}')
                        if orderInfo['orderStatus'] == 'TRADED':
                            orderInfo = dhanObj.getOrderStatus(orderid)
                            avgPrice = orderInfo['averageTradedPrice']
                            sl=avgPrice + (avgPrice*(20/100))
                            risk = sl - avgPrice
                            target=avgPrice - risk*config.RR
                            logger.info(f'Order Executed at price {avgPrice}')
                            
                            config.POSITION_CONFIG = {'tsym': symInfo['SYMBOL_NAME'], 'security_id': orderInfo['securityId'], 'qty': qty, 
                                                'avgPrice': avgPrice,'SL': sl,'target': target}
                            logger.info(f'Position Config {config.POSITION_CONFIG}')
                            break
                        else:
                            logger.info(f'Order not executed yet, modify with new limit price')
                            limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'SELL')
                                    # modify order with new limit price
                                    # dhanObj.modifyOrder(orderid=orderid, limitPrice=limitPrice)
                        sleep(1)
                #tracking the stop loss and target
            elif openposition:

                    logger.info('Checking for SL and target')
                    
                    positionConfig = config.POSITION_CONFIG
                    ltp = dhanObj.getLtp(security_id, exchange='NSE_FNO')#provided the sec id of the position taken pf ce  
                    if ltp >= positionConfig['SL']:
                        logger.info(f'LTP {ltp} hit SL {positionConfig["SL"]}, closing position')
                        orderid = dhanObj.closePositionBySymQtyTransType(positionConfig['security_id'], positionConfig['qty'])#not giving trans type   as it will determine        
                        openposition=True #i dont want to take another position for that day if sl hit                
                    elif ltp <= positionConfig['target']:
                        logger.info(f'LTP {ltp} hit target {positionConfig["target"]}, closing position')
                        orderid = dhanObj.closePositionBySymQtyTransType(positionConfig['security_id'], positionConfig['qty'])
                        openposition=True #i dont want to take another position for that day if target hit 
                    
                    
        except Exception as e:
            logger.exception('Error in scanning condition 1')
            
        sleep(1)
            

def orderforcond2(dhanObj: 'DhanAPICleint', condition: str):
    symdf = config.MASTER_DF
    strikeGap = config.SYM_MAP[config.SYMBOL][1]
    spotID = config.SYM_MAP[config.SYMBOL][0]
    openposition=False  
    ce_position_open = True
    pe_position_open = True
    while utility.getTimeCondition():
        try:
            if condition == 'neutral' and not openposition and condition != 'notrade':
                    openposition=True
                    from_date= datetime.now(config.TIME_ZONE) - timedelta(days=4)
                    logger.info('Placing sell order for pe ce both  a straddle ')
                    candledf = dhanObj.get_intraday_candles(security_id=config.SYM_MAP[config.SYMBOL][0],
                                                        exchange_segment='IDX_I', instrument_type='EQUITY',from_dt = from_date,timeFrame= config.TIMEFRAME,skipIncomplete=True)
                    lastcandle = candledf.iloc[-1]
                    strike=round(lastcandle.close/strikeGap)*strikeGap
                    logger.info(f'Strike selected  {strike}')
                    peStrike = strike - config.STRIKE_OFFSET*strikeGap
                    ceStrike = strike + config.STRIKE_OFFSET*strikeGap
                    symInfo_ce = symdf[(symdf['STRIKE_PRICE'] == ceStrike) & (symdf['OPTION_TYPE'] == 'CE')].iloc[0]
                    symInfo_pe = symdf[(symdf['STRIKE_PRICE'] == peStrike) & (symdf['OPTION_TYPE'] == 'PE')].iloc[0]
                    security_id_ce = symInfo_ce['SECURITY_ID']
                    security_id_pe = symInfo_pe['SECURITY_ID']
                    #placing sell order for ce and updating it 
                    qty = config.MULTIPLIER*int(symInfo_ce['LOT_SIZE'])
                    limitPrice_ce = dhanObj.getLimitPrice(config.EXCNAHGE, security_id_ce,'BUY')
                    orderid_ce = dhanObj.placeOrder(security_id=str(security_id_ce), transType='BUY', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=limitPrice_ce, triggerPrice=0)
                    logger.info(f'Order placed with order id  {orderid_ce}  with strike {strike} in ce')                    
                    #placing sell order for pe 
                    qty = config.MULTIPLIER*int(symInfo_pe['LOT_SIZE'])
                    limitPrice_pe = dhanObj.getLimitPrice(config.EXCNAHGE, security_id_pe,'BUY')
                    orderid_pe = dhanObj.placeOrder(security_id=str(security_id_pe), transType='BUY', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=limitPrice_pe, triggerPrice=0)
                    logger.info(f'Order placed with order id {orderid_pe}  with strike {strike} in pe ')  
                    for i in range(10):
                        orderInfo_ce = dhanObj.getOrderStatus(orderid_ce)
                        orderInfo_pe = dhanObj.getOrderStatus(orderid_pe)
                        logger.info(f'Order Status for CE {orderInfo_ce} ')
                        logger.info(f'Order Status for PE {orderInfo_pe} ')
                        
                        if orderInfo_ce['orderStatus'] == 'TRADED' and orderInfo_pe['orderStatus'] == 'TRADED':
                            orderInfo_ce = dhanObj.getOrderByID(orderid_ce)
                            orderInfo_pe= dhanObj.getOrderByID(orderid_pe)
                            avgPrice_ce = orderInfo_ce['averageTradedPrice']
                            sl_ce=avgPrice_ce + (avgPrice_ce*(20/100))
                            risk_ce = sl_ce - avgPrice_ce
                            target_ce=avgPrice_ce - risk_ce*config.RR
                            logger.info(f'Order Executed at price {avgPrice_ce}')
                            config.POSITION_CONFIG['ce']= {'tsym': symInfo_ce['SYMBOL_NAME'], 'security_id': security_id_ce, 'qty': qty, 
                                                      'avgPrice': avgPrice_ce,'SL': sl_ce,'target': target_ce}
                            logger.info(f'Position Config {config.POSITION_CONFIG["ce"]}')
                            avgPrice_pe = orderInfo_pe['averageTradedPrice']
                            sl_pe=avgPrice_pe + (avgPrice_pe*(20/100))  
                            risk_pe = sl_pe - avgPrice_pe
                            target_pe=avgPrice_pe - risk_pe*config.RR
                            logger.info(f'Order Executed at price {avgPrice_pe}')
                            config.POSITION_CONFIG['pe']= {'tsym': symInfo_pe['SYMBOL_NAME'], 'security_id': security_id_pe, 'qty': qty, 
                                                      'avgPrice': avgPrice_pe,'SL': sl_pe,'target': target_pe}
                            logger.info(f'Position Config {config.POSITION_CONFIG["pe"]}')
                            break
                        else:
                            if orderInfo_ce['orderStatus'] == 'TRADED' and orderInfo_pe['orderStatus'] != 'TRADED':
                                logger.info(f'Order of pe not executed yet, modify with new limit price')
            
                                limitPrice_pe = dhanObj.getLimitPrice(config.EXCNAHGE, security_id_ce,'SELL')
                                orderid_pe = dhanObj.placeOrder(security_id=str(security_id_pe), transType='BUY', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=limitPrice_pe, triggerPrice=0)
                                logger.info(f'Modified order for PE with new limit price {limitPrice_pe} and order id {orderid_pe}')
                            elif orderInfo_ce['orderStatus'] != 'TRADED' and orderInfo_pe['orderStatus'] == 'TRADED':
                                logger.info(f'Order of ce not executed yet, modify with new limit price')
                                limitPrice_ce = dhanObj.getLimitPrice(config.EXCNAHGE, security_id_ce,'SELL')
                                orderid_ce = dhanObj.placeOrder(security_id=str(security_id_ce), transType='BUY', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=limitPrice_ce, triggerPrice=0)
                                logger.info(f'Modified order for CE with new limit price {limitPrice_ce} and order id {orderid_ce}')
                            
                            elif orderInfo_ce['orderStatus'] != 'TRADED' and orderInfo_pe['orderStatus'] != 'TRADED':
                                logger.info(f'Both order not executed yet, modify with new limit price')
                                limitPrice_ce = dhanObj.getLimitPrice(config.EXCNAHGE, security_id_ce,'SELL')
                                orderid_ce = dhanObj.placeOrder(security_id=str(security_id_ce), transType='BUY', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=limitPrice_ce, triggerPrice=0)      
                                logger.info(f'Modified order for CE with new limit price {limitPrice_ce} and order id {orderid_ce}')
                                limitPrice_pe = dhanObj.getLimitPrice(config.EXCNAHGE, security_id_pe,'SELL')
                                orderid_pe = dhanObj.placeOrder(security_id=str(security_id_pe), transType='BUY', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=limitPrice_pe, triggerPrice=0)  
                                logger.info(f'Modified order for PE with new limit price {limitPrice_pe} and order id {orderid_pe}')    
                                
                                
                                
                            # modify order with new limit price
                            # dhanObj.modifyOrder(orderid=orderid, limitPrice=limitPrice)
                        sleep(1)  
            #sl tracking for both ce and pe                       
            elif openposition:       
                    logger.info('Checking for SL and target for both ce and pe')
                    positionConfig_ce = config.POSITION_CONFIG['ce']
                    positionConfig_pe = config.POSITION_CONFIG['pe']
                    ltp_ce = dhanObj.getLtp(int(positionConfig_ce['security_id']))#provided the sec id of the position taken pf ce  
                    ltp_pe = dhanObj.getLtp(int(positionConfig_pe['security_id']))#provided the sec id of the position taken pf pe  
                    
                    if ltp_ce >= positionConfig_ce['SL'] and ce_position_open:
                        logger.info(f'LTP {ltp_ce} hit SL {positionConfig_ce["SL"]} for CE, closing position')
                        orderid_ce= dhanObj.closePositionBySymQtyTransType(positionConfig_ce['security_id'], positionConfig_ce['qty'])
                        ce_position_open=False 
                        #it will tell that ce position hit sl
                        
                         
                    elif ltp_ce <= positionConfig_ce['target'] and ce_position_open:
                        logger.info(f'LTP {ltp_ce} hit target {positionConfig_ce["target"]} for CE, closing position')
                        orderid_ce = dhanObj.closePositionBySymQtyTransType(positionConfig_ce['security_id'], positionConfig_ce['qty'])
                        ce_position_open=False 
                        #openposition=False    
                    
                    if ltp_pe >= positionConfig_pe['SL'] and pe_position_open:
                        logger.info(f'LTP {ltp_pe} hit SL {positionConfig_pe["SL"]} for PE, closing position')
                        orderid_pe= dhanObj.closePositionBySymQtyTransType(positionConfig_pe['security_id'], positionConfig_pe['qty'])
                        pe_position_open=False 
                        #it will tell that pe position hit sl
                    elif ltp_pe <= positionConfig_pe['target'] and pe_position_open:
                        logger.info(f'LTP {ltp_pe} hit target {positionConfig_pe["target"]} for PE, closing position')
                        orderid_pe = dhanObj.closePositionBySymQtyTransType(positionConfig_pe['security_id'], positionConfig_pe['qty'])
                        pe_position_open=False 
                        #openposition=False
        except Exception as e:
            logger.exception('Error in scanning condition 2')
            
        sleep(1)
        
        
# def orderforcond3(dhanObj: 'DhanAPICleint', condition: str):
#     symdf = config.MASTER_DF
#     strikeGap = config.SYM_MAP[config.SYMBOL][1]
#     spotID = config.SYM_MAP[config.SYMBOL][0]
#     openposition=False
#     while utility.getTimeCondition():
#         try:
#             if condition == 'strong_sell'  and not openposition and condition != 'notrade':
#                     logger.info('Placing strong sell order for CE ')
#                     candledf = dhanObj.get_intraday_candles(security_id=config.SYM_MAP[config.SYMBOL][0],
#                                                         exchange_segment='IDX_I', instrument_type='EQUITY',from_dt = datetime.now(config.TIME_ZONE),timeFrame= config.TIMEFRAME,skipIncomplete=True)
#                     lastcandle = candledf.iloc[-1]
#                     strike=int(lastcandle.close/strikeGap)*strikeGap
#                     ceStrike = strike + config.STRIKE_OFFSET*strikeGap
#                     openposition=True
#                     #sell ce at ce strike
#                     symInfo = symdf[(symdf['STRIKE_PRICE'] == ceStrike) & (symdf['OPTION_TYPE'] == 'CE')].iloc[0]
#                     logger.info(f'Placing strong sell order for CE {symInfo["SYMBOL_NAME"]} at strike {ceStrike}')
#                     #placing order for CE
#                     security_id = symInfo['SECURITY_ID']
#                     qty = config.MULTIPLIER*int(symInfo['LOT_SIZE'])
#                     limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'SELL')
#                     orderid = dhanObj.placeOrder(security_id=str(security_id), transType='SELL', exchange=config.EXCNAHGE, qty=qty, orderType='LIMIT', productType= config.PRODUCT_TYPE, limitPrice=limitPrice, triggerPrice=0)
                    
#                     logger.info(f'Placed strong sell order for CE {symInfo["SYMBOL_NAME"]} with order id {orderid}')
#                     for i in range(10):
#                         orderInfo = dhanObj.getOrderStatus(orderid)
#                         logger.info(f'Order Status {orderInfo}')
#                         if orderInfo['orderStatus'] == 'TRADED':
#                             orderInfo = dhanObj.getOrderByID(orderid)
#                             avgPrice = orderInfo['averageTradedPrice']
#                             sl=avgPrice + (avgPrice*(20/100))
#                             risk = sl - avgPrice
#                             target=avgPrice - risk*config.RR
#                             logger.info(f'Order Executed at price {avgPrice}')
#                             config.POSITION_CONFIG = {'tsym': symInfo['SYMBOL_NAME'], 'security_id': security_id, 'qty': qty, 
#                                                 'avgPrice': avgPrice,'SL': sl,'target': target}
#                             logger.info(f'Position Config {config.POSITION_CONFIG}')
#                             break
#                         else:
#                             logger.info(f'Order not executed yet, modify with new limit price')
#                             limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'BUY')
#                                     # modify order with new limit price
#                                     # dhanObj.modifyOrder(orderid=orderid, limitPrice=limitPrice)
#                         sleep(1)
                    
#             if condition == 'strong_buy'  and not openposition and condition != 'notrade':
#                     logger.info('Placing strong sell order for PE i.e. upside view ')
#                     candledf = dhanObj.get_intraday_candles(security_id=config.SYM_MAP[config.SYMBOL][0],
#                                                         exchange_segment='IDX_I', instrument_type='EQUITY',from_dt = datetime.now(config.TIME_ZONE),timeFrame= config.TIMEFRAME,skipIncomplete=True)
#                     lastcandle = candledf.iloc[-1]
#                     strike=int(lastcandle.close/strikeGap)*strikeGap
#                     peStrike = strike - config.STRIKE_OFFSET*strikeGap
#                     openposition=True
#                     #sell pe at pe strike
#                     symInfo = symdf[(symdf['STRIKE_PRICE'] == peStrike) & (symdf['OPTION_TYPE'] == 'PE')].iloc[0]
#                     logger.info(f'Placing strong sell order for PE {symInfo["SYMBOL_NAME"]} at strike {peStrike}')
#                     #placing order for PE
#                     security_id = symInfo['SECURITY_ID']
#                     qty = config.MULTIPLIER*int(symInfo['LOT_SIZE'])
#                     limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'SELL')
#                     orderid = dhanObj.placeOrder(security_id=str(security_id), transType='SELL', exchange=config.EXCNAHGE, qty=qty, orderType='LIMIT', productType= config.PRODUCT_TYPE, limitPrice=limitPrice, triggerPrice=0)
                    
#                     logger.info(f'Placed sell order for PE {symInfo["SYMBOL_NAME"]} with order id {orderid}')
                                        
                    
#                     #check order is exexuted or not
#                     for i in range(10):
#                         orderInfo = dhanObj.getOrderStatus(orderid)
#                         logger.info(f'Order Status {orderInfo}')
#                         if orderInfo['orderStatus'] == 'TRADED':
#                             orderInfo = dhanObj.getOrderByID(orderid)
#                             avgPrice = orderInfo['averageTradedPrice']
#                             sl=avgPrice + (avgPrice*(20/100))
#                             risk = sl - avgPrice
#                             target=avgPrice - risk*config.RR
#                             logger.info(f'Order Executed at price {avgPrice}')
#                             config.POSITION_CONFIG = {'tsym': symInfo['SYMBOL_NAME'], 'security_id': security_id, 'qty': qty, 
#                                                 'avgPrice': avgPrice,'SL': sl,'target': target}
#                             logger.info(f'Position Config {config.POSITION_CONFIG}')
#                             break
#                         else:
#                             logger.info(f'Order not executed yet, modify with new limit price')
#                             limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'SELL')
#                                     # modify order with new limit price
#                                     # dhanObj.modifyOrder(orderid=orderid, limitPrice=limitPrice)
#                         sleep(1)
#                 #tracking the stop loss and target
#             elif openposition:

#                     logger.info('Checking for SL and target')
                    
#                     positionConfig = config.POSITION_CONFIG
#                     ltp = dhanObj.getLtp(int(positionConfig['security_id']), exchange='IDX_I')#provided the sec id of the position taken pf ce  
#                     if ltp >= positionConfig['SL']:
#                         logger.info(f'LTP {ltp} hit SL {positionConfig["SL"]}, closing position')
#                         orderid = dhanObj.closePositionBySymQtyTransType(positionConfig['security_id'], positionConfig['qty'])#not giving trans type   as it will determine        
#                         openposition=True #i dont want to take another position for that day if sl hit                
#                     elif ltp <= positionConfig['target']:
#                         logger.info(f'LTP {ltp} hit target {positionConfig["target"]}, closing position')
#                         orderid = dhanObj.closePositionBySymQtyTransType(positionConfig['security_id'], positionConfig['qty'])
#                         openposition=True #i dont want to take another position for that day if target hit 
                    
                    
#         except Exception as e:
#             logger.exception('Error in scanning condition 1')
            
#         sleep(1)



def main():
    
   
    # startTime =  datetime.now(config.TIME_ZONE)
    # closingTime = startTime.replace(hour=config.START_TIME[0], minute=config.START_TIME[1],second=config.START_TIME[2])
    # secondsToWait = max(0,(closingTime - startTime).total_seconds())
    # logger.info(f'Waiting for {secondsToWait} seconds to start the strategy')
    # sleep(secondsToWait)
    dhanObj = DhanAPICleint()
    utility.intializeMasterSym()
    dhanObj.startWebsocket()
    condition = getcondition(dhanObj)
    logger.info(f'Condition is {condition}')
    #orderforcond2(dhanObj,'neutral')
    
    #orderforcond2(dhanObj,'neutral')
    #orderforcond3()
    # atr = calculateATR(dhanObj)
    # threading.Thread(target=orderforcond1, args=(dhanObj, condition)).start()
    # threading.Thread(target=orderforcond2, args=(dhanObj,condition)).start()
    # threading.Thread(target=orderforcond3, args=(dhanObj,condition)).start()

    
    # caculateWIV(dhanObj)
    #sqaureOff(dhanObj)
    dhanObj.close_connection()

if __name__ == "__main__":
    main()  