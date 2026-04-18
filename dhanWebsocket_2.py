

from datetime import datetime
import threading,asyncio
stop_event = threading.Event()
import time
from dhanhq import DhanContext, MarketFeed,OrderUpdate
client_id = '1100265717'
access_token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzc0NTA0ODYzLCJpYXQiOjE3NzQ0MTg0NjMsInRva2VuQ29uc3VtZXJUeXBlIjoiQVBQIiwiZGhhbkNsaWVudElkIjoiMTEwMDI2NTcxNyJ9.wHkKSVv6pXIcEDHrwuJzC8tePUzg1aqoX3EOTumey5r3nzdnZMBcDMrbzd8ldrW4XBKJoVhmfIklfc-dHKC2Jg'



from queue import Queue, Empty
data_queue = Queue()
cmd_queue = Queue()
stop_event = threading.Event()

ltpFeed = {}
orderUpte = {}

def subscribe_symbols(symbols):
    cmd_queue.put(("SUB", symbols))


def unsubscribe_symbols(symbols):
    cmd_queue.put(("UNSUB", symbols))


def close_connection():
    cmd_queue.put(("CLOSE", None))
    stop_event.set()#stops immediately

stopLoop = True
# {'type': 'Ticker Data', 'exchange_segment': 1, 'security_id': 1333, 'LTP': '840.95', 'LTT': '13:28:21'}
def data_consumer():
    print(f" ==========  Starting consumer thread ===========")
    while not stop_event.is_set():
        try:
            tick = data_queue.get(timeout=1)
            if tick and 'type' in  tick and 'security_id' in tick : 
                ltpFeed[tick['security_id']] = {'ltp':float(tick['LTP'])}
            print("TICK:", tick)

            
        except Empty:
            pass
        except Exception:
            print('error in read feed data')


    print(f" ==========  Closing consumer thread ===========")

def markeFeedWorker(dhan_context):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    instruments = [(MarketFeed.IDX, "13", MarketFeed.Quote) ]
    version = "v2"

    feed = None
    while not stop_event.is_set() :
        try:
            print("Connecting websocket...")
            feed = MarketFeed(dhan_context, instruments, version)
            feed.run_forever()
            print("Websocket connected")

            while not stop_event.is_set():
                try:
                    tick = feed.get_data()
                    if tick:
                        data_queue.put(tick)
                except:
                    raise Exception("Feed dropped")

                # ---- command processing ----
                try:
                    cmd, payload = cmd_queue.get_nowait()

                    if cmd == "SUB":
                        feed.subscribe_symbols(payload)
                        instruments.extend(payload)

                    elif cmd == "UNSUB":
                        feed.unsubscribe_symbols(payload)

                    elif cmd == "CLOSE":
                        feed.close_connection()
                        print(f" ==========  Closing connection ===========")
                        time.sleep(2)
                        stop_event.set()
                        break

                except Empty:
                    pass
                except Exception as e:
                    print("Error in command processing :", e)

               

        except Exception as e:
            print("Websocket error:", e)
            if feed:
                try:
                    feed.close_connection()
                except Exception as e1 :
                    print(f"Error during feed disconnect {e1}")
            print("Reconnecting in 3 seconds...")
            time.sleep(3)



def on_order_update(order_data: dict):
    """Optional callback function to process order data"""
    print(f'Custom: {order_data["Data"]}')
    orderUpte [order_data["orderNo"]] = order_data["Data"]

def run_order_update(dhan_context):
    order_client = OrderUpdate(dhan_context)

    # Optional: Attach a callback function to receive and process order data.
    order_client.handle_order_update = on_order_update

    while True:
        try:
            order_client.connect_to_dhan_websocket_sync()
        except Exception as e:
            print(f"Error connecting to Dhan WebSocket: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)

def orderUpdatThreaed(dhan_context):
    while datetime.now().time() < datetime.strptime("15:29:00", "%H:%M:%S").time():
        # ordrbook = dhan_context.getOrderList()
        # for i in ordrbook:
        #     orderUpte[ordrbook.id]  = ordrbook
        
        # sleep(4)
        pass
          



def main():
    dhan_context = DhanContext(client_id, access_token)

    ws_thread=threading.Thread(target=markeFeedWorker, args=(dhan_context,), daemon=True)
    ows_thread=threading.Thread(target=run_order_update, args=(dhan_context,), daemon=True)
    data_thread=threading.Thread(target=data_consumer, daemon=True)
    #order_thread = threading.Thread(target=orderUpdatThreaed,args=(dhan_context,), daemon=True)
    ws_thread.start()
    data_thread.start()
    ows_thread.start()
    print("System online. Main thread is fully free.")
    
    # time.sleep(5)
    # print("----------- Subscribe ------------")
    # subscribe_symbols([(MarketFeed.NSE_FNO, "62609", MarketFeed.Ticker)])


    # time.sleep(5)
    # print("----------- UNSubscribe ------------")
    # unsubscribe_symbols([(MarketFeed.NSE, "1333", MarketFeed.Ticker)])


    # time.sleep(5)
    # close_connection()

    print("------------------")
    try:
        while datetime.now().time() < datetime.strptime("23:29:00", "%H:%M:%S").time():
            print(f"Main thread heartbeat...{ltpFeed}" )
            # orderUpte[567893884930]
            ## add your logic
            #close_connection()
            time.sleep(5)
    except KeyboardInterrupt: 
        print("Close system ")
    
    stop_event.set()
    ws_thread.join()
    print("System shutdown complete.")


if __name__ == '__main__':
    main()





"""
{'exchange': 'NSE', 'segment': 'E', 'source': 'W', 
'securityId': '11630', 'clientId': '1100089959',
 'exchOrderNo': '1200000080741389', 'orderNo':
   '351260318338501', 'product': 'I',
     'txnType': 'B', 'orderType': 'LMT', 
     'validity': 'DAY', 'remainingQuantity': 1,
       'quantity': 1, 'price': 377, 'strategyId': 'NA',
         'offMktFlag': '0', 'orderDateTime': '2026-03-18 14:25:47',
           'exchOrderTime': '2026-03-18 14:25:47', 
           'lastUpdatedTime': '2026-03-18 14:25:47',
 'remarks': ' ', 'mktType': 'NL', 'reasonDescription': 'CONFIRMED',
   'legNo': 1, 'instrument': 'EQUITY', 'symbol': 'NTPC',
     'productName': 'INTRADAY', 'status': 'Pending', 
     'lotSize': 1, 'expiryDate': '0001-01-01 00:00:00',
       'optType': 'XX', 'displayName': 'NTPC', 
       'isin': 'INE733E01010', 'series': 'EQ',
         'goodTillDaysDate': '2026-03-18', 
         'refLtp': 379.65, 'tickSize': 0.05, 'algoId': '0', 'multiplier': 1, 'correlationId': 'NA'}

         


         {'exchange': 'NSE', 'segment': 'E',
           'source': 'W', 'securityId': '11630',
             'clientId': '1100089959',
               'exchOrderNo': '1200000080741389',
                 'orderNo': '351260318338501', 'product': 'I', 'txnType': 'B',
                   'orderType': 'MKT', 'validity': 'DAY', 'quantity': 1, 'tradedQty': 1,
                     'tradedPrice': 379.55, 'avgTradedPrice': 379.55, 'strategyId': 'NA', 
                     'offMktFlag': '0', 'orderDateTime': '2026-03-18 14:28:40', 
                     'exchOrderTime': '2026-03-18 14:28:40', 
                     'lastUpdatedTime': '2026-03-18 14:28:40',
                       'remarks': ' ', 'mktType': 'NL',
                         'reasonDescription': 'TRADE CONFIRMED', 
                         'legNo': 1, 'instrument': 'EQUITY', 
                         'symbol': 'NTPC', 'productName': 'INTRADAY', 
                         'status': 'Traded', 'lotSize': 1, 'expiryDate': '0001-01-01 00:00:00', 'optType': 'XX', 'displayName': 'NTPC', 'isin': 'INE733E01010', 'series': 'EQ', 'goodTillDaysDate': '2026-03-18', 'refLtp': 379.4, 'tickSize': 0.05, 'algoId': '0', 'multiplier': 1, 'correlationId': 'NA'}
"""





















# Ticker:
# 
# {'type': 'Ticker Data', 'exchange_segment': 1, 'security_id': 383, 'LTP': '397.40', 'LTT': '15:01:27'}
#{'type': 'Ticker Data', 'exchange_segment': 1, 'security_id': 383, 'LTP': '397.20', 'LTT': '15:01:28'}


# quote

#{'type': 'OI Data', 'exchange_segment': 2, 'security_id': 40472, 'OI': 11760060}
#{'type': 'Quote Data', 'exchange_segment': 2, 'security_id': 40472, 'LTP': '51.65',
#  'LTQ': 65, 'LTT': '15:03:45', 'avg_price': '54.01', 'volume': 165829495, 
# 'total_sell_quantity': 1894360, 'total_buy_quantity': 3256045, 'open': '65.00',
#  'close': '68.40', 'high': '70.70', 'low': '42.55'}

# Full

#{'type': 'Full Data', 'exchange_segment': 2, 
# 'security_id': 40472, 'LTP': '48.05', 'LTQ': 65, 'LTT': '15:04:57',
#  'avg_price': '53.99', 'volume': 166578230, 'total_sell_quantity': 1892865,
#  'total_buy_quantity': 3146975, 'OI': 11760060, 'oi_day_high': 12791805, 
# 'oi_day_low': 7970105, 'open': '65.00', 'close': '68.40', 'high': '70.70',
#  'low': '42.55', 'depth': [{'bid_quantity': 130, 'ask_quantity': 1885, 
# 'bid_orders': 1, 'ask_orders': 9, 'bid_price': '48.05', 'ask_price': '48.10'}, 
# {'bid_quantity': 585, 'ask_quantity': 6110, 'bid_orders': 3, 'ask_orders': 20,
#  'bid_price': '48.00', 'ask_price': '48.15'}, 
# {'bid_quantity': 2275, 'ask_quantity': 4485, 
# 'bid_orders': 12, 'ask_orders': 17, 'bid_price': '47.95', 
# 'ask_price': '48.20'}, {'bid_quantity': 4615, 'ask_quantity': 3575,
#  'bid_orders': 20, 'ask_orders': 15, 'bid_price': '47.90', 'ask_price': '48.25'}, 
# {'bid_quantity': 5330, 'ask_quantity': 2405, 
# 'bid_orders': 12, 'ask_orders': 11, 'bid_price': '47.85', 'ask_price': '48.30'}]}