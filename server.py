
from autobahn.asyncio.websocket import (WebSocketServerFactory,
                                        WebSocketServerProtocol)

from call_types import channel_attr_calls, user_calls, voip_calls
from utilities import *

import asyncio
import json
import logging
import random
import ssl


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
logger = logging.getLogger('agsigserver')


class SignalProtocol(WebSocketServerProtocol):

    def __init__(self):
        super(self.__class__, self).__init__()

    def onConnect(self, request):
        logger.info('Client connecting {0}'.format(request .peer))

    def onOpen(self):
        logger.info('Websocket connection open.')

    def onMessage(self, payload, isBinary):
        if isinstance(payload, bytes):
            # The builtin json package can only take `str` instead of `bytes`.
            payload = payload.decode('utf8')

        message = json.loads(payload)

        cmd = message[0]

        if cmd == 'login':
            ret = self.process_login(message)
            ret = json.dumps(ret).encode('utf8')
            self.sendMessage(ret)
        elif cmd == 'call2':
            ret = self.process_call2(message)
            ret = json.dumps(ret).encode('utf8')
            self.sendMessage(ret)

            if message[1][0] == 'user_logout':
                logger.info('User is logging out.')
                self.sendClose()

    def onClose(self, wasClean, code, reason):
        logger.warning('WebSocket connection closed: {0}, '
                       'wasClean? {1}; code is : {2}'
                       .format(reason, wasClean, code))


    def process_call2(self, message):
        """Process all call2 requests.

        Args:
            message (str): Full message from the client.

        Returns:
            ret (list): The response message.
        """
        func_str, call_id, args = message[1]
        #ret = functions_dict[func_str](**args)

        ret = failed('unknown')

        if func_str in user_calls:
            user = get_user_by_line( args.get('line', '') )
            if user is None:
                ret = failed('wrong line')

            ret = getattr(user, func_str)(**args)
        elif func_str in channel_attr_calls:
            line = args.get('line', '')
            user = get_user_by_line(line)

            channel_name = args.get('channel', '')
            channel = get_channel_by_vid_name(user.vid, channel_name)

            attr_name = args.get('name', '')
            attr_value = args.get('value', '')

            if func_str == 'channel_set_attr':
                ret = channel.set_attr(user.account, user.uid,
                                       line, attr_name, attr_value)
            elif func_str == 'channel_del_attr':
                ret = channel.del_attr(user.account, user.uid,
                                       line, attr_name)
            elif func_str == 'channel_clear_attr':
                ret = channel.clear_attr(user.account, user.uid, line)
        elif func_str == 'channel_sendmsg':
            line = args.get('line', '')
            user = get_user_by_line(line)

            channel_name = args.get('name', '')
            channel = get_channel_by_vid_name(user.vid, channel_name)

            msg = args.get('msg', '')

            # Disable forcefully send a channel message, which means a user
            # must present in the channel.
            force = False

            ret = channel.send_msg(user.account, user.uid, line, msg, force)
        elif func_str == 'channel_leave':
            line = args.get('line', '')
            user = get_user_by_line(line)

            channel_name = args.get('channel', '')
            channel = get_channel_by_vid_name(user.vid, channel_name)

            ret = channel.leave(user.account, user.uid, line)
        elif func_str in voip_calls:
            line = args.get('line', '')
            user = get_user_by_line(line)

            channel_name = args.get('channelName', '')
            peer = args.get('peer', '')
            extra = args.get('extra', '')

            ret = user.voip_invite(func_str, channel_name, line, peer, extra)

        return ['call2-ret', [call_id, "", json.dumps(ret)]]

    def process_login(self, message):
        """Process client login request.

        Args:
            message (str): Full message from the client.

        Returns:
            ret (list): The response message.
        """
        args = message[1]
        account = args['account']
        device = args['device']
        ip = ''
        token = args['token']
        uid = 0
        ver = '' # args['ver']
        vid = ''

        # todo : check token
        args['conn'] = self
        args['ip'] = ''

        user = get_user_by_appid_account ( vid, account, create=True)
        ret = user.user_login(**args)

        return ['login_ret', ['', json.dumps(ret)]]



        # A string of integers.
        line = self.generate_line()

        # Possible values are ok, unknown, and failed.
        result = 'ok'

        # A 10-digit user id.
        uid = 1234567890

        data = json.dumps({'line': line, 'result': result, 'uid': uid})

        # The defaault error message is an empty string.
        error = ''

        #ret = json.dumps(['login_ret', [error, data]]).encode('utf8')
        ret = ['login_ret', [error, data]]

        return ret


class Server(object):
    """A websocket server class."""

    def __init__(self, loop = asyncio.get_event_loop()):
        self.factory = WebSocketServerFactory('ws://0.0.0.0:9000')
        self.factory.protocol = SignalProtocol

        coro = loop.create_server(self.factory, '0.0.0.0', 9000)
        self.server = loop.run_until_complete(coro)

    def close(self):
        self.server.close()

class ServerSSL(object):
    """A websocket server class."""

    def __init__(self, loop = asyncio.get_event_loop()):

        sslcontext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        sslcontext.load_cert_chain(certfile='server.crt', keyfile='server.key')

        self.factory = WebSocketServerFactory('wss://0.0.0.0:9001')
        self.factory.protocol = SignalProtocol

        coro = loop.create_server(self.factory, '0.0.0.0', 9001, ssl=sslcontext)
        self.server = loop.run_until_complete(coro)

    def close(self):
        self.server.close()

def demo_server(PORT=8080):
    def x():
        import http.server
        import socketserver

        Handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print("HTTP serving at port", PORT)
            httpd.serve_forever()
    import threading
    threading.Thread(target=x).start()

if __name__ == '__main__':
    server = Server()
    serverSSL = ServerSSL()

    try:
        demo_server()
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        asyncio.get_event_loop().close()
        server.close()
        serverSSL.close()
        import os
        os._exit()

