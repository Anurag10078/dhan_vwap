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
from typing import TYPE_CHECKING
from dhanhq import MarketFeed
from brokerClass import  DhanAPICleint
import pandas as pd


from brokerClass import DhanAPICleint
def ce_sec_id(dhanObj:DhanAPICleint,ltp_spot):
    try:
        masterdf=config.MASTER_DF
        current_strike=round(ltp_spot/50)*50
        final_strike_ce=current_strike+config.TILL_OTM*50
        requiredce=masterdf[(masterdf['STRIKE_PRICE']>=current_strike) & (masterdf['STRIKE_PRICE']<=final_strike_ce) & (masterdf['OPTION_TYPE']=='CE')]
        sec_ce_list=requiredce.SECURITY_ID.tolist()
        res=dhanObj.get_ticker_response(instrument=sec_ce_list)
        new_res=res['data']['data']['NSE_FNO']
        df = pd.DataFrame.from_dict(new_res, orient='index')
        df.reset_index(inplace=True)
        df.rename(columns={'index': 'security_id'}, inplace=True)
        target=100 #we will give the target in our util function 
        idx = (df['last_price'] - target).abs().idxmin()
        closest_id = df.loc[idx, 'security_id']
        closest_price = df.loc[idx, 'last_price']
        logger.info(f'Closest CE strike price is {closest_price} with security id {closest_id}')
        order_ce(dhanObj,closest_id)
    except Exception as e:
        logger.error(f'Error in ce_sec_id function {e}')

def pe_sec_id(dhanObj:DhanAPICleint,ltp_spot):
    try:
        masterdf=config.MASTER_DF
        current_strike=round(ltp_spot/50)*50
        final_strike_pe=current_strike-config.TILL_OTM*50
        requiredpe=masterdf[(masterdf['STRIKE_PRICE']<=current_strike) & (masterdf['STRIKE_PRICE']>=final_strike_pe) & (masterdf['OPTION_TYPE']=='PE')]
        sec_pe_list=requiredpe.SECURITY_ID.tolist()
        res=dhanObj.get_ticker_response(instrument=sec_pe_list)
        new_res=res['data']['data']['NSE_FNO']
        df = pd.DataFrame.from_dict(new_res, orient='index')
        df.reset_index(inplace=True)
        df.rename(columns={'index': 'security_id'}, inplace=True)
        target=100 #we will give the target in our util function 
        idx = (df['last_price'] - target).abs().idxmin()
        closest_id = df.loc[idx, 'security_id']
        closest_price = df.loc[idx, 'last_price']
        logger.info(f'Closest PE strike price is {closest_price} with security id {closest_id}')
        order_pe(dhanObj,closest_id)
    except Exception as e:
        logger.error(f'Error in pe_sec_id function {e}')

def order_ce(dhanObj:DhanAPICleint,sec_id):
    symdf = config.MASTER_DF
    symInfo=symdf[symdf['SECURITY_ID']==sec_id]
    strike=symInfo['STRIKE_PRICE'].values[0]
    logger.info(f'Placing order for strike price {strike}')
    openposition=False
    ce_adjustment=False
    sl_hit=False
    while utility.getTimeCondition():
        try:
            if not openposition:
                #place order for ce
                qty = config.MULTIPLIER*int(symInfo['LOT_SIZE'])
                openposition=True
                limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, sec_id,'SELL')
                orderid = dhanObj.placeOrder(security_id=str(sec_id), transType='SELL', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType = config.PRODUCT_TYPE, limitPrice=limitPrice, triggerPrice=0)
                logger.info(f'Placed order for CE {symInfo["SYMBOL_NAME"]} with order id {orderid}')
                dhanObj.subscribe_symbols([(MarketFeed.NSE_FNO,str(sec_id), MarketFeed.Ticker)])
                #check order is exexuted or not
                for i in range(10):
                    orderInfo = dhanObj.getOrderStatus(orderid)
                    logger.info(f'Order Status {orderInfo}')
                    if orderInfo['orderStatus'] == 'TRADED':
                        orderInfo = dhanObj.getOrderByID(orderid)
                        avgPrice1 = orderInfo['averageTradedPrice']
                        sl=2*avgPrice1
                        adjust=0.6*avgPrice1
                        
                        logger.info(f'Order Executed at price {avgPrice1}')
                        config.POSITION_CONFIG_CE[0] = {'tsym': symInfo['SYMBOL_NAME'], 'security_id': orderInfo['securityId'], 'qty': qty, 
                                                'avgPrice': avgPrice1,'SL': sl,'ADJUST': adjust}
                        logger.info(f'Position Config {config.POSITION_CONFIG_CE[0]}')
                        break
                    else:
                            logger.info(f'Order not executed yet, modify with new limit price')
                            limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE,sec_id,'SELL')
                                    # modify order with new limit price
                                    #(orderid=orderid, limitPrice=limitPrice)
                    sleep(1)
                       
            elif openposition :
                positionConfig = config.POSITION_CONFIG_CE[0]
                ltp=dhanObj.getLtp(sec_id,config.EXCNAHGE)
                if ltp>=positionConfig['SL'] and sl_hit==False:
                    sl_hit=True
                    orderid = dhanObj.closePositionBySymQtyTransType(positionConfig['security_id'], positionConfig['qty'],transType='SELL')
                    logger.info(f'SL hit for CE,closing position with order id {orderid}')
                    
                #now we will check for adjustment 
                elif sl_hit==False and ltp<=positionConfig['ADJUST'] and ce_adjustment==False:
                        ce_adjustment=True
                        logger.info(f'Price reached for adjustment, placing order for next strike')
                        #place order in same strike
                        limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, sec_id,'SELL')
                        orderid2 = dhanObj.placeOrder(security_id=str(sec_id), transType='SELL', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType = config.PRODUCT_TYPE, limitPrice=limitPrice, triggerPrice=0)
                        logger.info(f'Placed order for CE {symInfo["SYMBOL_NAME"]} with order id {orderid2}')
                        for i in range(10):
                            orderInfo = dhanObj.getOrderStatus(orderid2)
                            logger.info(f'Order Status {orderInfo}')
                            if orderInfo['orderStatus'] == 'TRADED':
                                orderInfo = dhanObj.getOrderByID(orderid2)
                                avgPrice2 = orderInfo['averageTradedPrice']
                                sl2=((config.POSITION_CONFIG_CE[0]['avgPrice']+avgPrice2)/2)*2
                                

                                logger.info(f'Order Executed at price {avgPrice2}')
                                config.POSITION_CONFIG_CE[1] = {'tsym': symInfo['SYMBOL_NAME'], 'security_id': orderInfo['securityId'], 'qty': qty, 
                                                        'avgPrice': avgPrice2,'SL': sl2}
                                logger.info(f'Position Config {config.POSITION_CONFIG_CE[1]}')
                                break   
                            else:
                                    logger.info(f'Order not executed yet, modify with new limit price')
                                    limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE,sec_id,'SELL')
                                            # modify order with new limit price
                                            #(orderid=orderid, limitPrice=limitPrice)
                            sleep(1)
                elif sl_hit == False and ce_adjustment==True:
                    
                        ltp=dhanObj.getLtp(sec_id,config.EXCNAHGE)
                        positionConfig = config.POSITION_CONFIG_CE[1]
                        if ltp>=positionConfig['SL']:
                            sl_hit=True
                            orderid = dhanObj.closePositionBySymQtyTransType(positionConfig['security_id'], positionConfig['qty'],transType='SELL')
                            logger.info(f'SL hit for 2 added position of ce,closing position with order id {orderid}')
                            
        except Exception as e:
            logger.error(f'Error in order_ce function {e}')
                    
        sleep(1)
def order_pe(dhanObj:DhanAPICleint,sec_id):
    symdf = config.MASTER_DF
    symInfo=symdf[symdf['SECURITY_ID']==sec_id]
    strike=symInfo['STRIKE_PRICE'].values[0]
    logger.info(f'Placing order for strike price {strike}')
    openposition=False
    pe_adjustment=False
    sl_hit=False
    while utility.getTimeCondition():
        try:
            if not openposition:
                #place order for pe
                qty = config.MULTIPLIER*int(symInfo['LOT_SIZE'])
                openposition=True
                limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE, sec_id,'SELL')
                orderid = dhanObj.placeOrder(security_id=str(sec_id), transType='SELL', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType = config.PRODUCT_TYPE, limitPrice=limitPrice, triggerPrice=0)
                logger.info(f'Placed order for PE {symInfo["SYMBOL_NAME"]} with order id {orderid}')
                dhanObj.subscribe_symbols([(MarketFeed.NSE_FNO,str(sec_id), MarketFeed.Ticker)])
                #check order is exexuted or not
                for i in range(10):
                    orderInfo = dhanObj.getOrderStatus(orderid)
                    logger.info(f'Order Status {orderInfo}')
                    if orderInfo['orderStatus'] == 'TRADED':
                        orderInfo = dhanObj.getOrderByID(orderid)
                        avgPrice1 = orderInfo['averageTradedPrice']
                        sl=2*avgPrice1
                        adjust=0.6*avgPrice1
                        
                        logger.info(f'Order Executed at price {avgPrice1}')
                        config.POSITION_CONFIG_PE[0] = {'tsym': symInfo['SYMBOL_NAME'], 'security_id': orderInfo['securityId'], 'qty': qty, 
                                                'avgPrice': avgPrice1,'SL': sl,'ADJUST': adjust}
                        logger.info(f'Position Config {config.POSITION_CONFIG_PE[0]}')
                        break
                    else:
                            logger.info(f'Order not executed yet, modify with new limit price')
                            limitPrice = dhanObj.getLimitPrice(config.EXCNAHGE,sec_id,'SELL')
                            orderid=dhanObj.placeOrder(security_id=str(sec_id), transType='SELL', exchnage=config.EXCNAHGE, qty=qty, orderType='LIMIT', prductType = config.PRODUCT_TYPE, limitPrice=limitPrice, triggerPrice=0)

                    sleep(1)
            elif openposition :
                positionConfig=config.POSITION_CONFIG_PE[0]
                Ltp=dhanObj.getLtp(security_id=sec_id)
                if Ltp>=positionConfig['SL'] and sl_hit==False:
                    sl_hit=True
                    orderid=dhanObj.closePositionBySymQtyTransType(security_id=sec_id,qty=positionConfig['qty'],transType='SELL')
                    logger.info(f'SL hit for PE,closing position with order id {orderid}')
                elif sl_hit==False and Ltp<=config.POSITION_CONFIG_PE['ADJUST'] and pe_adjustment==False :
                    pe_adjustment=True
                    logger.info(f'Price reached for the pe ajdustment,adding new position')
                    limitPrice2=dj=dhanObj.getLimitPrice(seg=config.EXCNAHGE,secid=sec_id,transtype='SELL')
                    orderid2=dhanObj.placeOrder(security_id=sec_id,exchnage=config.EXCNAHGE,transType='SELL',qty=qty,limitPrice=limitPrice2)
                    logger.info(f'Placed new sell order with Orderid={orderid2}')
                    #checking if order is executed or not 
                    for i in range(10):
                        orderInfo=dhanObj.getOrderByID(orderid=orderid2)
                        if orderInfo['orderStatus']=='TRADED':
                            avgPrice2=orderInfo['averageTradedPrice']
                            sl2=((avgPrice1+avgPrice2)/2)*2
                            logger.info(f'second order of PE ececuted at {avgPrice2}')
                            config.POSITION_CONFIG_PE[1]={'sym':symInfo['SYMBOL_NAME'], 'security_id': sec_id, 'qty': qty, 'avgPrice': avgPrice2, 'SL': sl2}
                            break
                        else:
                            logger.info("second order of pe is not ececuted yet")
                            limitPrice2=dj=dhanObj.getLimitPrice(seg=config.EXCNAHGE,secid=sec_id,transtype='SELL')
                            orderid2=dhanObj.placeOrder(security_id=sec_id,exchnage=config.EXCNAHGE,transType='SELL',qty=qty,limitPrice=limitPrice2)
                            
                        sleep(1)
                elif sl_hit==False and pe_adjustment==True and Ltp>=config.POSITION_CONFIG_PE[1]['SL']:
                    sl_hit=True
                    dhanObj.closePositionBySymQtyTransType(security_id=sec_id,qty=qty,transType='SELL')
                    logger.info(f'SL hit for 2 added position of ce,closing position with order id {orderid}')      
                
        except Exception as e:
            logger.error(f'Error in order_pe function {e}')
        sleep(1)         
                    
   

def main( ):
    
    utility.intializeMasterSym()
    dhanObj = DhanAPICleint()
    spot_ltp=dhanObj.getLtp(security_id=config.SYM_MAP['NIFTY'][0],exchange='IDX_I')
    thread1 = threading.Thread(target=ce_sec_id, args=(dhanObj, spot_ltp))
    thread2 = threading.Thread(target=pe_sec_id, args=(dhanObj, spot_ltp))
    thread1.start()
    thread2.start()
    # startTime =  datetime.now(config.TIME_ZONE)
    # closingTime = startTime.replace(hour=config.START_TIME[0], minute=config.START_TIME[1],second=config.START_TIME[2])
    # secondsToWait = max(0,(closingTime - startTime).total_seconds())
    # logger.info(f'Waiting for {secondsToWait} seconds to start the strategy')
    # sleep(secondsToWait)
    #dhanObj.startWebsocket()
    
    
    
    
    



    #atr = calculateATR(dhanObj)
    #threading.Thread(target=orderforcond1, args=(dhanObj, condition)).start()
    #threading.Thread(target=orderforcond2, args=(dhanObj,condition)).start()
    #threading.Thread(target=orderforcond3, args=(dhanObj,condition)).start()

    #dhanObj.startWebsocket()
    #caculateWIV(dhanObj)
    #sqaureOff(dhanObj)
    dhanObj.close_connection()

if __name__ == "__main__":
    main()  