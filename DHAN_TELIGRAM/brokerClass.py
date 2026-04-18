from time import time,sleep
from zoneinfo import ZoneInfo
import json,asyncio
from dhanhq import DhanContext, dhanhq ,MarketFeed ,OrderUpdate
from datetime import datetime,timedelta
import math
import requests
import pyotp
from decimal import Decimal
import logging,threading
from collections import defaultdict
import pandas as pd
logger = logging.getLogger(__name__)
import utility,config

from queue import Queue, Empty


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def __init__(cls, name, bases, dct):
        if bases:
            raise TypeError(f"{name} cannot inherit from {bases}")
        super().__init__(name, bases, dct)

class DhanAPICleint(metaclass=SingletonMeta):
    def __init__(self):
        self.dhan :dhanhq | None  = None
        self.dhan_context =None
        self.dhanDataws = None
        self.dhanOrderws =None
        self.liveFeed = {}
        self.orderPool = {}
        self.accessToken = None
        self.instruments = [(MarketFeed.IDX, "13", MarketFeed.Ticker)]
        self.clientId =  config.CLIENT_ID
        self.pin =  config.PIN
        self.totpToken =  config.TOTP_TOKEN
        self.timeZone = ZoneInfo("Asia/Kolkata")
        self.ordertag = 'DFT'
        self.startTime  = time()
        self.data_queue = Queue()
        self.cmd_queue = Queue()
        self.stop_event = threading.Event()
        self.start = time()
        self.tickStore = defaultdict(list)
        self.tickStoreLock = threading.Lock()
        self.login()
    
    # def login(self):
    #     url = "https://auth.dhan.co/app/generateAccessToken"
    #     max_retries = 3
    #     retry_count = 0
        
    #     while retry_count < max_retries:
    #         try:
    #             params = {
    #                 "dhanClientId": self.clientId,
    #                 "pin": self.pin,
    #                 "totp": pyotp.TOTP(self.totpToken).now()
    #             }

    #             response = requests.post(url, params=params)
    #             data = response.json()
    #             logger.info(f'Login response : {data}')
                
    #             if 'accessToken' in data:
    #                 accessToken = data['accessToken']
    #                 self.dhan_context = DhanContext(self.clientId, accessToken)
    #                 self.dhan = dhanhq(self.dhan_context)
    #                 logger.info("Login successful")
    #                 return
    #             else:
    #                 retry_count += 1
    #                 if retry_count < max_retries:
    #                     logger.warning(f"Login failed, retrying ({retry_count}/{max_retries})...")
    #                     sleep(2)
    #                 else:
    #                     logger.error("Login failed after 3 attempts")
    #                     raise Exception("Failed to obtain access token")
                        
    #         except Exception as e:
    #             retry_count += 1
    #             if retry_count < max_retries:
    #                 logger.warning(f"Login error: {e}, retrying ({retry_count}/{max_retries})...")
    #                 sleep(2)
    #             else:
    #                 logger.error(f"Login failed after 3 attempts: {e}")
    #                 raise


    def login(self):
        accessToken = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzc0NjcxMzk2LCJpYXQiOjE3NzQ1ODQ5OTYsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAwMDg5OTU5In0.JeRjxAx4al5GddqJIr2RwGqv8_drY4vnIg-IsRyIBul1Az_MaAs0gc2-ME7a-9j4Gc_U9MbHGFtsrTXplY6BLQ'
        self.dhan_context = DhanContext(self.clientId,accessToken)
        self.dhan = dhanhq(self.dhan_context)
    
    def truncate(self, number, tick_size=0.05, floor_or_ceil=None):
        if not number :
            return number
        tick_size = Decimal(tick_size)
        number = Decimal(number)
        remainder = number % tick_size
        if remainder == 0:
            number = number
        if floor_or_ceil is None:
            floor_or_ceil = 'ceil' if (remainder >= tick_size / 2) else 'floor'
        if floor_or_ceil == 'ceil':
            number = number - remainder + tick_size
        else:
            number = number - remainder
        number_of_decimals = len(format(Decimal(repr(float(tick_size))), 'f').split('.')[1])
            
        number = round(number, number_of_decimals)
        return float(number)
    
    # price = getLimitPrice(dhan.NSE,10666,'BUY')

    def getLimitPrice(self,seg:str,secid :int,transtype:str):
        limitPrice = 0
        try:
            
            qEres=  self.dhan.quote_data(securities = {seg:[int(secid)]})

            mod = qEres['data']['data'][seg][str(secid)]['depth']
            if transtype == 'BUY':
                limitPrice = float(mod['sell'][1]['price'])
            else:
                limitPrice = float(mod['buy'][1]['price'])
        except Exception :
            logger.exception(f'Error in getting limitPrice')
        return limitPrice


    def placeOrder(self,security_id,transType, exchnage ,qty,orderType = 'LIMIT' ,prductType = 'INTRADAY' ,limitPrice = 0 ,triggerPrice = 0):

        orderRes = self.dhan.place_order(security_id=security_id,   #hdfcbank
                exchange_segment=exchnage,    #  NSE_EQ , BSE_EQ, NSE_FNO,MCX_COMM , NSE_CURRENCY
                transaction_type=transType,  # BUY , SELL
                quantity=qty,
                order_type=orderType,   #  MARKET , LIMIT ,STOP_LOSS, STOP_LOSS_MARKET
                product_type=prductType,  # INTRADAY,  MARGIN,  CNC
                price=self.truncate(limitPrice),
                trigger_price = self.truncate(triggerPrice),
                tag=self.ordertag)

        logger.info(f'Order placed for {security_id} {transType} {qty} {orderType} limitPrice {limitPrice} triggerPrice {triggerPrice} \n {orderRes}')
        if orderRes['status'] == 'success':
            return  orderRes['data']['orderId']


    '''
    {'dhanClientId': '1100089959', 'orderId': '241260209361101', 'exchangeOrderId': '0', 
    'correlationId': 'DFT', 'orderStatus': 'REJECTED', 'transactionType': 'BUY',
      'exchangeSegment': 'NSE_EQ', 'productType': 'INTRADAY', 'orderType': 'MARKET',
        'validity': 'DAY', 'tradingSymbol': 'PNB', 'securityId': '10666', 'quantity': 1, 
        'disclosedQuantity': 0, 'price': 0.0, 'triggerPrice': 0.0, 'afterMarketOrder': False,
          'boProfitValue': 0.0, 'boStopLossValue': 0.0, 'legName': 'NA', 
          'createTime': '2026-02-09 12:09:29', 'updateTime': '2026-02-09 12:09:29',
            'exchangeTime': '0001-01-01 00:00:00', 'drvExpiryDate': '0001-01-01',
              'drvOptionType': 'NA', 'drvStrikePrice': 0.0, 'omsErrorCode': '0',
                'omsErrorDescription': 'RMS:241260209361101:You have insufficient funds. Please add Rs.23.70 to trade.',
                  'algoId': '0', 'remainingQuantity': 1, 'averageTradedPrice': 0.0, 'filledQty': 0}
    
    '''


    '''
    Feed
    {'exchange': 'NSE', 'segment': 'E', 'source': 'W',
      'securityId': '10666', 'clientId': '1100089959', 'exchOrderNo': '0',
        'orderNo': '341260209256501', 'product': 'I', 'txnType': 'B',
          'orderType': 'MKT', 'validity': 'DAY', 'remainingQuantity': 1, 
          'quantity': 1, 'strategyId': 'NA', 'offMktFlag': '0', 
          'orderDateTime': '2026-02-09 12:12:09', 
          'exchOrderTime': '0001-01-01 00:00:00', 
          'lastUpdatedTime': '2026-02-09 12:12:09', 
          'remarks': ' ', 'mktType': 'NL', 
          'reasonDescription': 'RMS:341260209256501:You have insufficient funds. Please add Rs.23.67 to trade.',
            'legNo': 1, 'instrument': 'EQUITY', 'symbol': 'PNB', 
            'productName': 'INTRADAY', 'status': 'Rejected', 'lotSize': 1,
              'expiryDate': '0001-01-01 00:00:00', 'optType': 'XX',
                'displayName': 'Punjab National Bank', 'isin': 'INE160A01022', 'series': 'EQ', 
                'goodTillDaysDate': '2026-02-09', 'refLtp': 124.05, 'tickSize': 0.01, 'algoId': '0', 
                'multiplier': 1, 'correlationId': 'NA'}
    
    '''

    def getOrderStatus( self, orderid):
        orderid = str(orderid)
        for _ in range(6):
            try:
                if orderid in  self.orderPool:
                    return self.orderPool[orderid]
                logger.info(f"Order {orderid} not found in order pool  : {self.orderPool.keys()}")
                sleep(1)
                return self.getOrderByID(orderid)
            except :
                logger.exception(f'Error in fetching order Status')


    def isAllOrderTraded(self,orderlist):
        try:
            completeCount = 0
            for orderid in orderlist:
                orderDetail = self.getOrderStatus(orderid)
                if orderDetail['orderStatus'] == 'TRADED':
                    completeCount =completeCount + 1
            return len(orderlist) == completeCount
            
        except Exception:
            logger.exception(f'Error in checking all orders')


    def getOrderBook(self):
        try:
            orderRes = self.dhan.get_order_list()
            if orderRes is not None and  orderRes['status'] == 'success':
                return pd.DataFrame(orderRes['data'])
        except:
            logger.exception(f'Error in orderList')

    # placeOrder(self,security_id,transType, exchnage ,qty,orderType = 'LIMIT' ,prductType = 'INTRADAY' ,limitPrice = 0 ,triggerPrice = 0):
    def closePositionBySymQtyTransType(self,security_id,qty,transType):
        posRes =   self.dhan.get_positions()
        if posRes is None:
            return
        for position in posRes['data']:
            try:
                sym = position['tradingSymbol']
                netQty =int(position['netQty'])
                if position['netQty'] != 0 and position['securityId'] ==  str(security_id)  and ((transType == 'BUY' and netQty > 0) or  (transType == 'SELL' and netQty < 0)):   
                    transType = 'BUY' if position['netQty'] < 0  else 'SELL'
                    logger.info(f'Close {sym} {netQty} ')
                    limitPrice = self.getLimitPrice(position['exchangeSegment'], position['securityId'], transType)
                    exitOrderid = self.placeOrder(security_id = position['securityId'],exchnage= position['exchangeSegment'] , transType=transType, 
                            qty = min(abs(netQty) ,qty) ,orderType = 'LIMIT' ,prductType = position['productType'],limitPrice=limitPrice)
                    return exitOrderid
            except Exception as e:
                logger.exception(f"Error in closing Positon {security_id} ")


    def closeAllPositions(self):
        posRes =   self.dhan.get_positions()
        if posRes is None:
            return
        for position in posRes['data']:
            try:
                sym = position['tradingSymbol']
                netQty =int(position['netQty'])
                if position['netQty'] != 0 and position['exchangeSegment'] == config.EXCNAHGE and position['productType'] == config.PRODUCT_TYPE :   
                    transType = 'BUY' if position['netQty'] < 0  else 'SELL'
                    logger.info(f'Close {sym} {netQty} ')
                    limitPrice = self.getLimitPrice(position['exchangeSegment'], position['securityId'], transType)
                    exitOrderid = self.placeOrder(security_id = position['securityId'],exchnage= position['exchangeSegment'] , transType=transType, 
                            qty =abs(netQty) ,orderType = 'LIMIT' ,prductType = position['productType'],limitPrice=limitPrice)
                    return exitOrderid
            except Exception as e:
                logger.exception(f"Error in closing Positon ")


    def getPositionBook(self):
        try:
            orderRes = self.dhan.get_positions()
            logger.info(f'Position book : {orderRes}')
            if orderRes is not None and  orderRes['status'] == 'success':
                return pd.DataFrame(orderRes['data'])
        except:
            logger.exception(f'Error in orderList')



    def getOrderByID(self,orderid):
        try:
            orderRes =  self.dhan.get_order_by_id(orderid)
            if orderRes is not None and  orderRes['status'] == 'success':
                return orderRes['data'][0]
        except:
            logger.exception(f'Error in getting orderInfo for {orderid}')



    def cancelOrderByID(self,orderid):
        try:
            cancelRes = self.dhan.cancel_order(orderid)
            logger.info(f'Order cancellation Response {cancelRes}')
        except:
            logger.exception(f'Error in order cancellation {orderid}')


    def cancelAllOpenOrder(self):
        try:
            orderdf = self.getOrderBook()
            for i in orderdf.index:
                order = orderdf.loc[i]
                if order['orderStatus'] not in ['TRADED','REJECTED','CANCELLED'] : # and order['algoId'] in self.ordertag:
                    self.cancelOrderByID(order['orderId'])
        except:
            logger.exception(f'Error in all order cancellation')

    def getExecutedPrice(self,orderid):    
        tradeRes = self.dhan.get_trade_book(orderid)
        if tradeRes is not None and  tradeRes['status'] == 'success' and len(tradeRes['data'])>0:
            tradedPrice = tradeRes['data'][0]['tradedPrice']
            return tradedPrice
        
        return 0

    def getOptionChain(self,index,expiry):
        try:
            optdata = self.dhan.option_chain(
            under_security_id=index,
            under_exchange_segment="IDX_I", # Index Option   #ya maina repositry la liya hai 
            expiry=expiry.strftime("%Y-%m-%d")            # Format: MM-DD-YYYY
            )
            filtered=optdata['data']['data']['oc']
            celist=[]
            pelist=[]
            for key,value in filtered.items():
                celist.append({**value['ce']['greeks'],**value['ce'],'strike':key})
                pelist.append({**value['pe']['greeks'],**value['pe'],'strike':key})
            cedf=pd.DataFrame(celist)
            del cedf['greeks']
            pedf=pd.DataFrame(pelist)
            del pedf['greeks']
            return cedf,pedf
        except:
            logger.exception(f'Error in fetching option chain for {index} {expiry}')
    
    
    
    def getLtpFromAPI(self,exchange,token):
        try:
            qres = self.dhan.quote_data(securities = {exchange: [int(token)]})
            if qres['status'] == 'success':
                lastPrice =  float(qres['data']['data'][exchange][str(token)]['last_price'])
                return  lastPrice
            else:
                logger.error(f'Error qres {exchange} {token} {qres}')
        except:
            logger.exception(f'Error in get ltp {exchange} {token}')


    def getLtp(self,security_id,exchange ='NSE_FNO'):
        security_id  = str(security_id)
        try:
            if security_id in  self.liveFeed:
                feedRes=  self.liveFeed[security_id]
                feedDelay =( datetime.now(self.timeZone) - feedRes['ltt']).total_seconds()
                if feedDelay > 120:
                    sleep(1)
                    return self.getLtpFromAPI(exchange=exchange,token = security_id)
                    #logger.info(f'Last trade time in {security_id} {tokenInfo.SEM_TRADING_SYMBOL} {feedDelay} ')
                return feedRes['ltp']
            else:
                return self.getLtpFromAPI(exchange=exchange,token = security_id)
        except:
            logger.exception("Error in get ltp")


    def data_consumer(self):
        while not self.stop_event.is_set():
            try:
                response = self.data_queue.get(timeout=1)

                if  response and response['type'] in ['Ticker Data' ,'Full Data']:
                        sec_id = str(response['security_id'])
                        ltp = float(response['LTP'])
                        ltt = datetime.strptime(f"{datetime.now(self.timeZone).date()} {response['LTT']}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=self.timeZone)
                        self.liveFeed[sec_id] = {'ltp': ltp, 'ltt': ltt}
                        with self.tickStoreLock:
                            ticks = self.tickStore[sec_id]
                            ticks.append({'price': ltp, 'timestamp': ltt})
                            if len(ticks) > 50000:
                                self.tickStore[sec_id] = ticks[-50000:]
                else:
                    logger.info(f"TICK: {response}")
                    
                if time() - self.start > 20:
                    logger.info(f"Tick : {response}" )
                    self.start = time()
                    logger.info(f"Feed : {len(self.liveFeed)} \n {pd.DataFrame(self.liveFeed.values())}" )
                
            except Empty:
                pass
            except Exception as e:
                logger.error(f'error in data consumer thread {e}')
    
    def subscribe_symbols(self,symbols):
        self.cmd_queue.put(("SUB", symbols))


    def unsubscribe_symbols(self,symbols):
        self.cmd_queue.put(("UNSUB", symbols))


    def close_connection(self):
        self.cmd_queue.put(("CLOSE", None))


    def markeFeedWorker(self,dhan_context):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        version = "v2"
      
        while not self.stop_event.is_set() :
            try:
                logger.info("Connecting websocket...")
                self.dhanDataws = MarketFeed(dhan_context, self.instruments, version)
                self.dhanDataws.run_forever()
                logger.info("Websocket connected")

                while not self.stop_event.is_set():
                    try:
                        tick = self.dhanDataws.get_data()
                        if tick:
                            self.data_queue.put(tick)
                    except:
                        raise Exception("Feed dropped")

                    # ---- command processing ----
                    try:
                        cmd, payload = self.cmd_queue.get_nowait()

                        if cmd == "SUB":
                            self.dhanDataws.subscribe_symbols(payload)
                            self.instruments.extend(payload)

                        elif cmd == "UNSUB":
                            self.dhanDataws.unsubscribe_symbols(payload)

                        elif cmd == "CLOSE":
                            self.dhanDataws.close_connection()
                            self.stop_event.set()
                            break

                    except Empty:
                        pass
                

            except Exception as e:
                logger.error(f"Websocket error: {e}" )
                if self.dhanDataws:
                    try:
                        self.dhanDataws.close_connection()
                    except Exception  :
                        logger.exception(f"Error during feed disconnect ")
                logger.debug("Reconnecting in 3 seconds...")
                sleep(3)




    def on_order_update(self,order_data: dict):
        # logger.info(f'Custom: {order_data["Data"]}')
        # self.orderPool[]  = order_data["Data"]
        if order_data.get('Type') == 'order_alert':
            data = order_data.get('Data', {})
            if "orderNo" in data:
                order_id = data["orderNo"]
                status = data.get("status", "Unknown status")
                data.update({'orderStatus':status.upper() })
                self.orderPool[order_id] = data
                logger.info(f"Status: {status}, Order ID: {order_id}, Data: {data}")
            else:
                logger.info(f"Order Update received: {data}")
        else:
            logger.info(f"Unknown message received: {order_data}")

    def run_order_update(self,dhan_context):
        order_client = OrderUpdate(dhan_context)

        order_client.handle_order_update = self.on_order_update

        while not self.stop_event.is_set():
            try:
                order_client.connect_to_dhan_websocket_sync()
            except Exception as e:
                logger.error(f"Error connecting to Dhan WebSocket: {e}. Reconnecting in 5 seconds...")
                sleep(5)



    def orderPool(self):
        while utility.getTimeCondition():
            try:
                orderRes = self.dhan.get_order_list()
                if orderRes is not None and  orderRes['status'] == 'success':
                    for order in orderRes['data']:
                        self.orderPool[order['orderId']] = order
                else:
                    logger.debug(f'Order res empty {orderRes}')
            except:
                logger.exception(f"Error in order update")
            sleep(2)


    def startWebsocket(self):
        ows_thread   = threading.Thread(target=self.run_order_update, args=(self.dhan_context,), daemon=True)
        ws_thread   = threading.Thread(target=self.markeFeedWorker, args=(self.dhan_context,), daemon=True)
        data_thread = threading.Thread(target=self.data_consumer, daemon=True)
        ws_thread.start()
        data_thread.start()
        ows_thread.start()
    
    def closeWebsocket(self):
        self.close_connection()
        self.stop_event.set()


    ### exchange_segment=> 'NSE_FNO'   , 'NSE_EQ' , 'IDX_I'

    ### instrument_type =>  'OPTIDX' , 'EQUITY' , 'INDEX'
  
    def get_intraday_candles(self, security_id, exchange_segment, instrument_type,
                            from_dt, to_dt=None, timeFrame=1, skipIncomplete= True, tz='Asia/Kolkata'):
        timeZone=ZoneInfo("Asia/Kolkata")
        # Convert datetime -> YYYY-MM-DD string for API
        from_str = from_dt.strftime('%Y-%m-%d')
        if to_dt is None:
            to_dt = datetime.now()  
            
        to_str   = to_dt.strftime('%Y-%m-%d')
        cres = self.dhan.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            from_date=from_str,
            to_date=to_str,
            interval=timeFrame
        )

        candledf = pd.DataFrame(cres['data'])
        candledf['timestamp'] = pd.to_datetime(candledf['timestamp'], unit='s', utc=True) .dt.tz_convert(tz)
        if skipIncomplete:
            recentTime = datetime.now(timeZone)
            startTime = recentTime.replace(hour=9, minute=15, second=0,microsecond=0)
            minFromStart = math.floor((datetime.now(timeZone) - startTime).seconds / 60)
            lastTf = int(minFromStart / timeFrame) * timeFrame - timeFrame
            lastTimeStamp = startTime + timedelta(minutes=lastTf)
            candledf = candledf[(candledf.timestamp <= lastTimeStamp)]
        return candledf


    def get_historical_daily_candles(self, security_id, exchange_segment, instrument_type,
                                 from_dt, to_dt, tz='Asia/Kolkata'):

        from_str = from_dt.strftime('%Y-%m-%d')
        to_str   = to_dt.strftime('%Y-%m-%d')

        hres = self.dhan.historical_daily_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            from_date=from_str,
            to_date=to_str
        )

        candledf = pd.DataFrame(hres['data'])

        candledf['timestamp'] = (
            pd.to_datetime(candledf['timestamp'], unit='s', utc=True)
            .dt.tz_convert(tz)
        )

        return candledf


    def get_live_candles(self, security_id, timeframe=1):
        security_id = str(security_id)
        with self.tickStoreLock:
            ticks = self.tickStore.get(security_id, [])[:]
        if not ticks:
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        df = pd.DataFrame(ticks)
        df = df.set_index('timestamp')

        market_open = df.index[0].normalize() + pd.Timedelta(hours=9, minutes=15)
        market_close = df.index[0].normalize() + pd.Timedelta(hours=15, minutes=30)
        df = df[(df.index >= market_open) & (df.index <= market_close)]
        if df.empty:
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        candledf  = df['price'].resample(f'{timeframe}min', origin=market_open).ohlc()
        candledf['volume'] = 0
        #candledf['volume'] = df['volume'].resample(f'{timeframe}min', origin=market_open).sum()
        candledf = candledf.reset_index()
        candledf.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        return candledf