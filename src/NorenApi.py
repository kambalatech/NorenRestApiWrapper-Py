import json
import requests
import threading
import websocket
import logging
import enum
import datetime
from time import sleep

from collections import OrderedDict
from collections import namedtuple

#python setup.py bdist_wheel --universal

Instrument = namedtuple('Instrument', ['exchange', 'token', 'symbol',
                                       'name', 'expiry', 'lot_size'])
logger = logging.getLogger(__name__)


class FeedType(enum.Enum):
    TOUCHLINE = 1    
    SNAPQUOTE = 2

class ProductType(enum.Enum):
    Delivery = 'C'
    Intraday = 'I'
    Normal   = 'M'
    
class PriceType(enum.Enum):
    Market = 'MKT'
    Limit = 'LMT'
    StopLossLimit = 'SL-LMT'
    StopLossMarket = 'SL-MKT'

class BuyorSell(enum.Enum):
    Buy = 'B'
    Sell = 'S'

def reportmsg(msg):
    #print(msg)
    logger.debug(msg)

class StarApi:
    __service_config = {
      'host': 'http://wsapihost/',
      'routes': {
          'authorize': '/QuickAuth',
          'placeorder': '/PlaceOrder',
          'modifyorder': '/ModifyOrder',
          'cancelorder': 'CancelOrder',
          'orderbook': '/OrderBook',
          'TPSeries' : '/TPSeries',
      },
      'websocket_endpoint': 'wss://wsendpoint/'
    }

    def __init__(self, host, wsendpoint):
        self.__service_config.host = host
        self.__service_config.websocket_endpoint = wsendpoint

        self.__websocket = None
        self.__websocket_connected = False
        self.__ws_mutex = threading.Lock()
        self.__on_error = None
        self.__on_disconnect = None
        self.__on_open = None
        self.__subscribe_callback = None
        self.__order_update_callback = None
        self.__market_status_messages_callback = None
        self.__exchange_messages_callback = None
        self.__oi_callback = None
        self.__dpr_callback = None
        self.__subscribers = {}
        self.__market_status_messages = []
        self.__exchange_messages = []

    def __ws_run_forever(self):
        
        while True:
            try:
                self.__websocket.run_forever()
            except Exception as e:
                logger.warning(f"websocket run forever ended in exception, {e}")
            
            sleep(0.1) # Sleep for 100ms between reconnection.

    def __ws_send(self, *args, **kwargs):
        while self.__websocket_connected == False:
            sleep(0.05)  # sleep for 50ms if websocket is not connected, wait for reconnection
        with self.__ws_mutex:
            ret = self.__websocket.send(*args, **kwargs)
        return ret

    def __on_close_callback(self, wsapp, close_status_code, close_msg):
        reportmsg(close_status_code)
        reportmsg(wsapp)

        self.__websocket_connected = False
        if self.__on_disconnect:
            self.__on_disconnect()

    def __on_open_callback(self, ws=None):
        self.__websocket_connected = True

        #prepare the data
        values              = { "t": "c" }
        values["uid"]       = self.__username
        values["pwd"]       = self.__password
        values["actid"]     = self.__username
        values["susertoken"]    = self.__susertoken
        values["source"]    = 'API'                

        payload = json.dumps(values)

        reportmsg(payload)
        self.__ws_send(payload)

        #self.__resubscribe()
        

    def __on_error_callback(self, ws=None, error=None):
        if(type(ws) is not websocket.WebSocketApp): # This workaround is to solve the websocket_client's compatiblity issue of older versions. ie.0.40.0 which is used in upstox. Now this will work in both 0.40.0 & newer version of websocket_client
            error = ws
        if self.__on_error:
            self.__on_error(error)

    def __on_data_callback(self, ws=None, message=None, data_type=None, continue_flag=None):
        #print(ws)
        #print(message)
        #print(data_type)
        #print(continue_flag)

        res = json.loads(message)

        if(self.__subscribe_callback is not None):
            if res['t'] == 'tk' or res['t'] == 'tf':
                self.__subscribe_callback(res)
                return

        if(self.__on_error is not None):
            if res['t'] == 'ck' and res['s'] != 'OK':
                self.__on_error(res)
                return

        if(self.__order_update_callback is not None):
            if res['t'] == 'om':
                self.__order_update_callback(res)
                return

        if self.__on_open:
            if res['t'] == 'ck' and res['s'] == 'OK':
                self.__on_open()
                return


    def start_websocket(self, subscribe_callback = None, 
                        order_update_callback = None,
                        socket_open_callback = None,
                        socket_close_callback = None,
                        socket_error_callback = None,
                        run_in_background=True,
                        market_status_messages_callback = None,
                        exchange_messages_callback = None,
                        oi_callback = None,
                        dpr_callback = None):        
        """ Start a websocket connection for getting live data """
        self.__on_open = socket_open_callback
        self.__on_disconnect = socket_close_callback
        self.__on_error = socket_error_callback
        self.__subscribe_callback = subscribe_callback
        self.__order_update_callback = order_update_callback
        self.__market_status_messages_callback = market_status_messages_callback
        self.__exchange_messages_callback = exchange_messages_callback
        self.__oi_callback = oi_callback
        self.__dpr_callback = dpr_callback
        url = self.__service_config['websocket_endpoint'].format(access_token=self.__susertoken)
        reportmsg('connecting to {}'.format(url))

        self.__websocket = websocket.WebSocketApp(url,
                                                on_data=self.__on_data_callback,
                                                on_error=self.__on_error_callback,
                                                on_close=self.__on_close_callback,
                                                on_open=self.__on_open_callback)
        #th = threading.Thread(target=self.__send_heartbeat)
        #th.daemon = True
        #th.start()
        #if run_in_background is True:
        self.__ws_thread = threading.Thread(target=self.__ws_run_forever)
        self.__ws_thread.daemon = True
        self.__ws_thread.start()
        
    
    def login(self, userid, password, twoFA, vendor_code, api_secret, imei):
        config = StarApi.__service_config

        #prepare the uri
        url = f"{config['host']}{config['routes']['authorize']}" 
        reportmsg(url)
        #prepare the data
        values              = { "source": "API" , "apkversion": "1.0.0"}
        values["uid"]       = userid
        values["pwd"]       = password
        values["factor2"]   = twoFA
        values["vc"]        = vendor_code
        values["appkey"]    = api_secret        
        values["imei"]      = imei        

        payload = 'jData=' + json.dumps(values)
        reportmsg("Req:" + payload)

        res = requests.post(url, data=payload)
        reportmsg("Reply:" + res.text)

        resDict = json.loads(res.text)
        if resDict['stat'] != 'Ok':            
            return None
        
        self.__username   = userid
        self.__accountid  = userid
        self.__password   = password
        self.__susertoken = resDict['susertoken']
        #reportmsg(self.__susertoken)

        return resDict

    def subscribe(self, instrument, feed_type=FeedType.TOUCHLINE):
        values = {}

        if(feed_type == FeedType.TOUCHLINE):
            values['t'] =  't'
        elif(feed_type == FeedType.SNAPQUOTE):
            values['t'] =  'd'
        
        if type(instrument) == list:
            values['k'] = '#'.join(instrument)
        else :
            values['k'] = instrument

        data = json.dumps(values)

        #print(data)
        self.__ws_send(data)

    def subscribe_orders(self):
        values = {'t': 'o'}
        values['actid'] = self.__accountid        

        data = json.dumps(values)

        reportmsg(data)
        self.__ws_send(data)


    def place_order(self, buy_or_sell, product_type,
                    exchange, tradingsymbol, quantity, discloseqty,
                    price_type, price=0.0, trigger_price=None,
                    retention='DAY', amo='NO', remarks=None):
        config = StarApi.__service_config

        #prepare the uri
        url = f"{config['host']}{config['routes']['placeorder']}" 
        print(url)
        #prepare the data
        values              = {'ordersource':'API'}
        values["uid"]       = self.__username
        values["actid"]     = self.__accountid
        values["trantype"]  = buy_or_sell.value
        values["prd"]       = product_type.value        
        values["exch"]      = exchange
        values["tsym"]      = tradingsymbol
        values["qty"]       = str(quantity)
        values["dscqty"]    = str(discloseqty)        
        values["prctyp"]    = price_type.value
        values["prc"]       = str(price)
        values["trgprc"]    = str(trigger_price)
        values["ret"]       = retention
        values["remarks"]   = remarks
        
        payload = 'jData=' + json.dumps(values) + f'&jKey={self.__susertoken}'
        
        print(payload)

        res = requests.post(url, data=payload)
        print(res.text)

        resDict = json.loads(res.text)
        if resDict['stat'] != 'Ok':            
            return None

        return resDict

    def modify_order(self, orderno, exchange, tradingsymbol, newquantity,
                    newprice_type, newprice=0.0, newtrigger_price=None, amo='NO'):
        config = StarApi.__service_config

        #prepare the uri
        url = f"{config['host']}{config['routes']['modifyorder']}" 
        print(url)

        #prepare the data
        values                  = {'ordersource':'API'}
        values["uid"]           = self.__username
        values["actid"]         = self.__accountid
        values["norenordno"]    = orderno
        values["exch"]          = exchange
        values["tsym"]          = tradingsymbol
        values["qty"]           = str(newquantity)
        values["prctyp"]        = newprice_type.value        
        values["prc"]           = str(newprice)        
        
        payload = 'jData=' + json.dumps(values) + f'&jKey={self.__susertoken}'
        
        print(payload)

        res = requests.post(url, data=payload)
        print(res.text)

        resDict = json.loads(res.text)
        if resDict['stat'] != 'Ok':            
            return None

        return resDict

    def cancel_order(self, orderno):
        config = StarApi.__service_config

        #prepare the uri
        url = f"{config['host']}{config['routes']['cancelorder']}" 
        print(url)

        #prepare the data
        values              = {'ordersource':'API'}
        values["uid"]       = self.__username
        values["norenordno"]    = orderno
        
        payload = 'jData=' + json.dumps(values) + f'&jKey={self.__susertoken}'
        
        print(payload)

        res = requests.post(url, data=payload)
        print(res.text)

        resDict = json.loads(res.text)
        if resDict['stat'] != 'Ok':            
            return None

        return resDict

    def get_order_book(self):
        config = StarApi.__service_config

        #prepare the uri
        url = f"{config['host']}{config['routes']['orderbook']}" 
        reportmsg(url)

        #prepare the data
        values              = {'ordersource':'API'}
        values["uid"]       = self.__username
        
        payload = 'jData=' + json.dumps(values) + f'&jKey={self.__susertoken}'
        
        reportmsg(payload)

        res = requests.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        
        #error is a json with stat and msg wchih we printed earlier.
        if type(resDict) != list:                            
                return None

        return resDict

    def get_time_price_series(self, exchange, token, starttime=None, endtime=None):
        config = StarApi.__service_config

        #prepare the uri
        url = f"{config['host']}{config['routes']['TPSeries']}" 
        reportmsg(url)

        #prepare the data
        if starttime == None:
            timestring = time.strftime('%d-%m-%Y') + ' 00:00:00'
            timeobj = time.strptime(timestring,'%d-%m-%Y %H:%M:%S')
            starttime = time.mktime(timeobj)

        #
        values              = {'ordersource':'API'}
        values["uid"]       = self.__username
        values["exch"]      = exchange
        values["token"]     = token
        values["starttime"] = starttime
        values["endtime"]   = endtime
        
        payload = 'jData=' + json.dumps(values) + f'&jKey={self.__susertoken}'
        
        reportmsg(payload)

        res = requests.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        
        #error is a json with stat and msg wchih we printed earlier.
        if type(resDict) != list:                            
                return None

        return resDict


