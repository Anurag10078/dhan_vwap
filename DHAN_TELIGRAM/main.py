import config
from logging import getLogger
from logger import setup_logging   
from datetime import datetime,  time as tt , timedelta
import utility
setup_logging()
logger = getLogger(__name__)
from time import sleep
import threading
import pandas_ta as ta
import pandas as pd

from brokerClass import  DhanAPICleint


def iv_calculation(dhanObj:DhanAPICleint,ltp,expiry,index,strike_gap):
    cedf,pedf = dhanObj.getOptionChain(index,expiry)
    pedf['strike']=pedf['strike'].astype(float).astype(int)
    cedf['strike']=cedf['strike'].astype(float).astype(int)
    current_strike= round(ltp/strike_gap)*strike_gap
    final_strike_ce=current_strike+strike_gap*config.WIV_STRIKE_RANGE
    final_strike_pe=current_strike-strike_gap*config.WIV_STRIKE_RANGE

    required_ce = cedf[((cedf['strike'] >= int(current_strike)) & (cedf['strike'] <= int(final_strike_ce)))]
    required_pe = pedf[((pedf['strike'] <= int(current_strike)) & (pedf['strike'] >= int(final_strike_pe)))]
    required_ce['delta_weighted_ce']=required_ce.delta*required_ce.implied_volatility
    required_pe['delta_weighted_pe']=required_pe.delta*required_pe.implied_volatility
    total_weighted_dlt = required_ce['delta_weighted_ce'].sum()+required_pe['delta_weighted_pe'].abs().sum()
    total_del=required_ce['delta'].sum()+required_pe['delta'].abs().sum()
    iv=total_weighted_dlt/total_del
    return iv


def caculateWIV(dhanObj:DhanAPICleint):
    while utility.getTimeCondition():
        try:
            indexConfig= config.SYM_MAP[config.SYMBOL]
            ltp =dhanObj.getLtp(security_id=indexConfig[0],exchange ='IDX_I')
            expiry = config.EXPIRY_LIST[0]  # STRTIME
            nextExpiry = config.EXPIRY_LIST[1]
            ivCurent = iv_calculation(dhanObj,ltp,expiry,index=indexConfig[0],strike_gap=indexConfig[1])
            ivNext = iv_calculation(dhanObj,ltp,nextExpiry,index=indexConfig[0],strike_gap=indexConfig[1])
            config.WIV  = 0.6*ivCurent + 0.4*ivNext
        except Exception as e:
            logger.exception('Error in calculating WIV')
        sleep(5)
    


def calculateATR(dhanObj:DhanAPICleint):
    indexConfig= config.SYM_MAP[config.SYMBOL]
    df = dhanObj.get_historical_daily_candles(security_id=indexConfig[0],exchange_segment='IDX_I', instrument_type='EQUITY',
                                 from_dt=datetime.now()-timedelta(days=15), to_dt=datetime.now())
    df['atr'] = ta.atr(df.high, df.low, df.close, length=config.IDX_ATR_PERIOD)
    df = df[df.timestamp.dt.date <= (datetime.now(config.TIME_ZONE).date() )]
    logger.info(f'ATR Calculation for {config.SYMBOL} is {df["atr"].iloc[-1]}')
    return df['atr'].iloc[-1]

def scanCond1(dhanObj:DhanAPICleint,atr:float):

    thresoldValue = atr*config.ATR_MULTIPLIER
    isPositionOpen = False
    symdf = config.MASTER_DF
    strikeGap = config.SYM_MAP[config.SYMBOL][1]
    spotID = config.SYM_MAP[config.SYMBOL][0]
    waitTillCandleClose = secTowaitFinishCandle()
    logger.info(f'Waiting for {waitTillCandleClose} seconds for the current candle to close')
    sleep(waitTillCandleClose + 10) 
    preCandledf = dhanObj.get_intraday_candles(security_id=config.SYM_MAP[config.SYMBOL][0],
                                                exchange_segment='IDX_I', instrument_type='EQUITY',from_dt = datetime.now(config.TIME_ZONE),timeFrame= config.TIMEFRAME)

    logger.info(f'Pre candledf \n {preCandledf.tail()}')

    while utility.getTimeCondition():
        try:
            if config.WIV is not None and config.WIV  < 100 and not isPositionOpen and utility.isEntryAllowed():
                candledf = dhanObj.get_live_candles(security_id=config.SYM_MAP[config.SYMBOL][0],timeframe= config.TIMEFRAME)
                
                logger.info(f'Live candledf \n {candledf.tail()}')
                candledf = pd.concat([preCandledf, candledf], ignore_index=True).drop_duplicates(subset='timestamp', keep='first') .sort_values('timestamp') .reset_index(drop=True)
                logger.info(f'Final candledf \n {candledf.tail()}')
                candledf['atr'] = ta.atr(candledf.high, candledf.low, candledf.close, length=config.IDX_ATR_PERIOD)
                logger.info(f'candledf for condition 1 {candledf.tail()}')
                recetnCandle = candledf.iloc[-1]
                candleLen = recetnCandle.high - recetnCandle.low
                if candleLen > thresoldValue:
                    isPositionOpen = True
                    config.IS_OPEN_POSITION = True
                    atmStrike = round(recetnCandle.close/strikeGap)*strikeGap
                    spotEntryLevel = recetnCandle.close
                    if recetnCandle.close > recetnCandle.open :
                        utility.printandSenMsg(f'Condition 1 met for short entry, buy PE ')

                        
                        strike = atmStrike - strikeGap*config.STRIKE_OFFSET
                        symInfo = symdf[(symdf['STRIKE_PRICE'] == strike) & (symdf['OPTION_TYPE'] == 'PE')].iloc[0]
                        logger.info(f'Placing order for {symInfo.DISPLAY_NAME} with strike {strike} for PE ')
                        isLong =  False
                        sl = recetnCandle.high + recetnCandle.atr
                        target = spotEntryLevel - abs(spotEntryLevel -sl)*config.RR

                    if recetnCandle.close < recetnCandle.open :
                        utility.printandSenMsg(f'Condition 1 met for long entry, BUY CE ')  # 3 sec


                        strike = atmStrike + strikeGap*config.STRIKE_OFFSET
                        symInfo = symdf[(symdf['STRIKE_PRICE'] == strike) & (symdf['OPTION_TYPE'] == 'CE')].iloc[0]
                        logger.info(f'Placing order for {symInfo.DISPLAY_NAME} with strike {strike} for CE ')
                        isLong =  True
                        sl = recetnCandle.low - recetnCandle.atr
                        target = spotEntryLevel + abs(spotEntryLevel -sl)*config.RR
                    
                    security_id = symInfo['SECURITY_ID']
                    qty = config.MULTIPLIER*int(symInfo['LOT_SIZE'])
                    limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'BUY')
                    orderid = dhanObj.placeOrder(security_id=str(security_id), transType='BUY', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=limitPrice, triggerPrice=0)
                    utility.printandSenMsg(f'Order placed with order id {orderid} for {"CE" if isLong else "PE"} with strike {strike}')
                    # check if order executed and if not then cancel the order
                    for i in range(10):
                        orderInfo = dhanObj.getOrderStatus(orderid)
                        logger.info(f'Order Status {orderInfo}')
                        if orderInfo['orderStatus'] == 'TRADED':
                            orderInfo = dhanObj.getOrderByID(orderid)
                            avgPrice = orderInfo['averageTradedPrice']
                            logger.info(f'Order Executed at price {avgPrice}')
                            config.POSITION_CONFIG = {'tsym': symInfo.SYMBOL_NAME, 'security_id': security_id, 'qty': qty, 
                                                      'spotEntryPrice': spotEntryLevel,'avgPrice': avgPrice,'SL': sl,'target': target,'isLong': isLong}
                            logger.info(f'Position Config {config.POSITION_CONFIG}')
                            break
                        else:
                            logger.info(f'Order not executed yet, modify with new limit price')
                            limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, security_id,'BUY')
                            # modify order with new limit price
                            # dhanObj.modifyOrder(orderid=orderid, limitPrice=limitPrice)
                        sleep(1)

            elif isPositionOpen:
                posConfig = config.POSITION_CONFIG
                spotLtp = dhanObj.getLtp(spotID, exchange='IDX_I')
                #isSquareOff = datetime.now(config.TIME_ZONE).time() >= utility.getTime(config.SquareOffTime)  # if time is more than 3:20 then square off the position   
                isSquareOff = False
                if posConfig['isLong']:
                    # for long position check for SL and target hit
                    if isSquareOff or (spotLtp <= posConfig['SL'] or spotLtp >= posConfig['target']):
                        utility.printandSenMsg(f'Exit Condition met for long position, place sell order')
                        orderid = dhanObj.closePositionBySymQtyTransType(posConfig['security_id'], posConfig['qty'], 'BUY')
                        utility.printandSenMsg(f'Exit Order placed with order id {orderid}')
                        isPositionOpen = False
                        config.IS_OPEN_POSITION = False
                else:
                    # for short position check for SL and target hit
                    if isSquareOff or (spotLtp >= posConfig['SL'] or spotLtp <= posConfig['target']):
                        logger.info(f'Exit Condition met for short position, place sell order')
                        orderid = dhanObj.closePositionBySymQtyTransType(posConfig['security_id'], posConfig['qty'], 'BUY')
                        logger.info(f'Exit Order placed with order id {orderid} ')
                        isPositionOpen = False
                        config.IS_OPEN_POSITION = False
              


        except Exception as e:
            logger.exception('Error in scanning condition 1')
        
        sleep(1 if isPositionOpen else 5)



def secTowaitFinishCandle():
    tf = config.TIMEFRAME
    currenttime =datetime.now(config.TIME_ZONE)
    minutes = (currenttime - timedelta(minutes=15)).minute
    remaintime = minutes%tf  
    interval = (tf -remaintime)*60 - currenttime.second
    return interval


import math
def scanCond2(dhanObj:DhanAPICleint):
    isPositionOpen = False
    symdf = config.MASTER_DF
    strikeGap = config.SYM_MAP[config.SYMBOL][1]
    spotID = config.SYM_MAP[config.SYMBOL][0]
    while utility.getTimeCondition():
        try:
            if config.WIV is not None and config.WIV  > 15 and not isPositionOpen and utility.isEntryAllowed():
                candledf = dhanObj.get_intraday_candles(security_id=config.SYM_MAP[config.SYMBOL][0],
                                                exchange_segment='IDX_I', instrument_type='EQUITY',from_dt = datetime.now(config.TIME_ZONE),timeFrame= config.TIMEFRAME)
                candledf['atr'] = ta.atr(candledf.high, candledf.low, candledf.close, length=config.IDX_ATR_PERIOD2)
                logger.info(f'candledf for condition 2 {candledf.tail()}')
                recetnCandle = candledf.iloc[-1]
                spotEntryLevel = recetnCandle.close
                atr15 = recetnCandle.atr
                if atr15 < (config.WIV/math.sqrt(252))*spotEntryLevel/100:
                    logger.info(f'Condition 2 met for  entry, buy CE and PE ')
                    atmStrike = round(recetnCandle.close/strikeGap)*strikeGap
                    strikeCE = atmStrike + strikeGap*config.STRIKE_OFFSET
                    strikePE = atmStrike - strikeGap*config.STRIKE_OFFSET
                    cesymInfo = symdf[(symdf['STRIKE_PRICE'] == strikeCE) & (symdf['OPTION_TYPE'] == 'CE')].iloc[0]
                    pesymInfo = symdf[(symdf['STRIKE_PRICE'] == strikePE) & (symdf['OPTION_TYPE'] == 'PE')].iloc[0]

                    logger.info(f'Placing order for {cesymInfo.DISPLAY_NAME} with strike {strikeCE} for CE ')
                    
                    ceSL = candledf.iloc[-6:]['low'].min() - recetnCandle.atr
                    peSL = candledf.iloc[-6:]['high'].max() + recetnCandle.atr

                    cetarget = spotEntryLevel + abs(spotEntryLevel -ceSL)*config.RR
                    petarget = spotEntryLevel - abs(spotEntryLevel -peSL)*config.RR


                    cesecurity_id = cesymInfo['SECURITY_ID']
                    ceQty = config.MULTIPLIER*int(cesymInfo['LOT_SIZE'])
                    celimitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, cesecurity_id,'BUY')
                    ceOrderid = dhanObj.placeOrder(security_id=str(cesecurity_id), transType='BUY', exchnage=config.EXCNAHGE, qty=ceQty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=celimitPrice, triggerPrice=0)
                    
                    #dhanObj.placeOrder(security_id=str(cesymInfo['SECURITY_ID']), transType='BUY', exchnage=config.EXCNAHGE, qty=config.MULTIPLIER*int(cesymInfo['LOT_SIZE']), orderType='LIMIT', prductType='INTRADAY', limitPrice=dhanObj.getLimitPrice(config.EXCNAHGE, cesymInfo['SECURITY_ID'],'BUY'), triggerPrice=0)

                    logger.info(f'Placing order for {pesymInfo.DISPLAY_NAME} with strike {strikePE} for PE ')
                    pesecurity_id = pesymInfo['SECURITY_ID']
                    peQty = config.MULTIPLIER*int(pesymInfo['LOT_SIZE'])
                    pelimitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, pesecurity_id,'BUY')
                    peOrderid = dhanObj.placeOrder(security_id=str(pesecurity_id), transType='BUY', exchnage=config.EXCNAHGE, qty=peQty, orderType='LIMIT', prductType= config.PRODUCT_TYPE, limitPrice=pelimitPrice, triggerPrice=0)

                    for _ in range(10):
                        isAllTraded = dhanObj.isAllOrderTraded([ceOrderid, peOrderid])
                        if isAllTraded:
                            logger.info(f'Both Orders Executed for CE and PE')

                            ceOrderInfo = dhanObj.getOrderByID(ceOrderid)
                            peOrderInfo = dhanObj.getOrderByID(peOrderid)
                            ceAvgPrice = ceOrderInfo['averageTradedPrice']
                            peAvgPrice = peOrderInfo['averageTradedPrice']
                            logger.info(f'CE Order Executed at price {ceAvgPrice} and PE Order Executed at price {peAvgPrice}')
                            config.POSITION_CONFIG = {'ce': {'tsym': cesymInfo.SYMBOL_NAME, 'security_id': str(cesymInfo.SECURITY_ID), 'qty': ceQty,'avgPrice': ceAvgPrice,'SL': ceSL,'target': cetarget}, 
                                                    'pe': {'tsym': pesymInfo.SYMBOL_NAME, 'security_id': str(pesymInfo.SECURITY_ID), 'qty': peQty,'avgPrice': peAvgPrice,'SL': peSL,'target': petarget}}
                        
                            logger.info(f'Position Config {config.POSITION_CONFIG}')
                            isPositionOpen = True
                            config.IS_OPEN_POSITION = True
                            break
                        sleep(1)
                    else:
                        logger.info(f'Orders not executed yet, canceling orders')
                        dhanObj.cancelOrderByID(ceOrderid)
                        dhanObj.cancelOrderByID(peOrderid)

            elif isPositionOpen:
                posConfig = config.POSITION_CONFIG
                #isSquareOff  = datetime.now(config.TIME_ZONE).time() >= utility.getTime(config.SquareOffTime)   # if time is more than 3:20 then square off the position
                isSquareOff = False
                spotLtp = dhanObj.getLtp(spotID, exchange='IDX_I')
                ceSL = posConfig['ce']['SL']
                peSL = posConfig['pe']['SL']
                ceTarget = posConfig['ce']['target']
                peTarget = posConfig['pe']['target']

                if isSquareOff or (spotLtp <= ceSL or spotLtp >= ceTarget):
                    logger.info(f'Exit Condition met for CE position, place sell order')
                    orderid = dhanObj.closePositionBySymQtyTransType(posConfig['ce']['security_id'], posConfig['ce']['qty'], 'BUY')
                    logger.info(f'Exit Order placed with order id {orderid} for CE ')
                    isPositionOpen = False
                    config.IS_OPEN_POSITION = False

                if isSquareOff or (spotLtp >= peSL or spotLtp <= peTarget):
                    logger.info(f'Exit Condition met for PE position, place sell order')
                    orderid = dhanObj.closePositionBySymQtyTransType(posConfig['pe']['security_id'], posConfig['pe']['qty'], 'BUY')
                    logger.info(f'Exit Order placed with order id {orderid} for PE ')
                    isPositionOpen = False
                    config.IS_OPEN_POSITION = False

        except Exception as e:
            logger.exception('Error in scanning condition 2')

        if not isPositionOpen:
            interval = secTowaitFinishCandle() 
            logger.info(f'Waiting for {interval} seconds to check for next candle')
        else:
            interval = 1
        sleep(interval)

def sqaureOff(dhanObj:DhanAPICleint):
    try:
        if config.IS_OPEN_POSITION:
            logger.info(f'Square off condition met, closing all positions')
            dhanObj.closeAllPositions()
            config.IS_OPEN_POSITION = False
    except Exception as e:
        logger.exception('Error in square off')


def main():

    utility.telegram_bot_sendtext('Strategy Started')
    startTime =  datetime.now(config.TIME_ZONE)
    closingTime = startTime.replace(hour=config.START_TIME[0], minute=config.START_TIME[1],second=config.START_TIME[2])
    secondsToWait = max(0,(closingTime - startTime).total_seconds())
    logger.info(f'Waiting for {secondsToWait} seconds to start the strategy')
    sleep(secondsToWait)

    utility.intializeMasterSym()
    dhanObj = DhanAPICleint()
    atr = calculateATR(dhanObj)
    threading.Thread(target=scanCond1, args=(dhanObj, atr)).start()
    # threading.Thread(target=scanCond2, args=(dhanObj,)).start()

    dhanObj.startWebsocket()
    caculateWIV(dhanObj)
    #sqaureOff(dhanObj)
    # sleep(10)
    # for i in range(60*60*6):  # run for 6 hours
    #     try:
    #         x = dhanObj.get_live_candles(security_id=13,timeframe=1)
    #         logger.info(x)
    #     except Exception as e:
    #         logger.exception('Error in getting live candles')
    #     sleep(1)
    dhanObj.close_connection()

if __name__ == "__main__":
    main()