"""This process obtains JSON representations of modified, created or deleted
database objects through ZeroMQ, and feeds them to browser clients
through a websocket."""
from __future__ import print_function
import signal
import time
import sys
from os import makedirs, access, R_OK, W_OK
from os.path import exists, dirname
import configparser
import traceback
from time import sleep
from datetime import timedelta
import logging
import logging.config

import asyncio
from aiohttp import web, WSMsgType
# import aiohttp_cors
import sockjs
import simplejson as json
import zmq
import zmq.asyncio
from zmq.eventloop import zmqstream, ioloop
from aiohttp_requests import requests

# from assembl.lib.zmqlib import INTERNAL_SOCKET
from assembl.lib.raven_client import setup_raven, capture_exception
from assembl.lib.web_token import decode_token, TokenInvalid

# Inspired by socksproxy.

log = logging.getLogger("assembl.tasks.changes_router")

SECTION = 'app:idealoom'
Everyone = 'system.Everyone'


def setup_async_loop():
    # while zmq < 17
    ctx = zmq.asyncio.Context()
    loop = zmq.asyncio.ZMQEventLoop()
    asyncio.set_event_loop(loop)
    # following https://github.com/zeromq/pyzmq/issues/1034
    zmq.asyncio.Socket.fileno = lambda self: self.FD
    return ctx, loop


def setup_router(in_socket, out_socket):
    td = zmq.devices.ProcessDevice(zmq.FORWARDER, zmq.XSUB, zmq.XPUB)
    td.bind_in(in_socket)
    td.bind_out(out_socket)
    td.setsockopt_in(zmq.IDENTITY, b'XSUB')
    td.setsockopt_out(zmq.IDENTITY, b'XPUB')
    td.start()


async def websocket_handler(request):
    # if we decide to replace sockjs with a pure websocket
    ws = web.WebSocketResponse()
    #  headers={
    #     "Access-Control-Allow-Origin": server_url,
    # })
    await ws.prepare(request)
    active_socket = ActiveSocket(ws)
    log.debug('new connection')
    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            if msg.data == 'close':
                await active_socket.on_close()
            else:
                await active_socket.on_message(msg.data)
                # await ws.send_str(msg.data + '/answer')
        elif msg.type == WSMsgType.ERROR:
            log.error('ws connection closed with exception %s' %
                  ws.exception())

    active_socket.on_close()

    return ws


def setup_app(path, server_url, loop):
    app = web.Application()
    # app.add_routes([web.get('/socket', websocket_handler)])
    # cors = aiohttp_cors.setup(app)
    # resource = cors.add(app.router.add_resource(path))
    # route = cors.add(
    #     resource.add_route("GET", websocket_handler), {
    #         server_url: aiohttp_cors.ResourceOptions(
    #             allow_credentials=True,
    #             expose_headers="*",
    #             allow_headers="*",
    #             max_age=3600,
    #         )})
    # https://github.com/aio-libs/sockjs/issues/38
    name = 'changes'
    manager = sockjs.SessionManager(
        name, app, ActiveSocket.sockjs_handler, loop,
        heartbeat=10, timeout=timedelta(seconds=30))
    sockjs.add_endpoint(
        app, ActiveSocket.sockjs_handler,
        name=name, prefix=path+"/", manager=manager)
    return app


class ActiveSocket(object):
    active_sockets = dict()

    @classmethod
    def setup(cls, zmq_context, token_secret, server_url, out_socket_name):
        cls.zmq_context = zmq_context
        cls.token_secret = token_secret
        cls.server_url = server_url
        cls.out_socket_name = out_socket_name

    def __init__(self, session):
        self.session = session
        # https://github.com/aio-libs/sockjs/issues/38
        # session.timeout = timedelta(seconds=60)
        self.active_sockets[session.id] = self
        self.valid = True

    token = None
    discussion = None
    userId = None
    task = None

    def on_open(self, request):
        self.valid = True
        self.closing = False

    @classmethod
    def by_session(cls, session):
        return cls.active_sockets.get(session.id, None)

    async def on_recv(self, data):
        try:
            data = data[-1].decode('utf-8')
            if '@private' in data:
                jsondata = json.loads(data)
                jsondata = [x for x in jsondata
                            if x.get('@private', self.userId) == self.userId]
                if not jsondata:
                    return
                data = json.dumps(jsondata)
            self.session.send(data)
            log.debug('sent:'+data)
        except Exception:
            capture_exception()
            await self.close()

    async def close(self):
        log.info("closing")
        if not self.valid:
            return
        self.valid = False
        self.active_sockets.pop(self.session.id, None)
        if self.task and not self.task.cancelled:
            self.task.cancel()
        if self.raw_token and self.discussion and self.userId != Everyone:
            await requests.post('%s/data/Discussion/%s/all_users/%d/disconnecting' % (
                self.server_url, self.discussion, self.token['userId']
                ), data={'token': self.raw_token})

    async def on_message(self, msg):
        try:
            if msg.startswith('discussion:') and self.valid:
                self.discussion = msg.split(':', 1)[1]
                log.debug('discussion_id: %s', self.discussion)
            if msg.startswith('token:') and self.valid:
                try:
                    self.raw_token = msg.split(':', 1)[1]
                    self.token = decode_token(self.raw_token, self.token_secret)
                    if self.token['userId'] != Everyone:
                        self.userId = 'local:Agent/' + str(
                            self.token['userId'])
                    else:
                        self.userId = Everyone
                    log.info('userId: %s', self.userId)
                except TokenInvalid:
                    pass
            if self.token and self.discussion:
                # Check if token authorizes discussion
                r = await requests.get(
                    '%s/api/v1/discussion/%s/permissions/Conversation.R/u/%s' % (
                        self.server_url, self.discussion, self.token['userId']
                        ), headers={"Accept": "application/json"})
                text = await r.text()
                log.debug(text)
                if text != 'true':
                    return
                log.info("connected")
                self.task = asyncio.create_task(self.connect())
                self.session.send('[{"@type":"Connection"}]')
                if self.token and self.raw_token and self.discussion and self.userId != Everyone:
                    await requests.post('%s/data/Discussion/%s/all_users/%d/connecting' % (
                        self.server_url, self.discussion, self.token['userId']
                        ), data={'token': self.raw_token})
        except Exception:
            capture_exception()
            await self.close()

    async def connect(self):
        sock = self.zmq_context.socket(zmq.SUB)
        try:
            sock.identity = b'SUB'
            sock.connect(self.out_socket_name)
            sock.subscribe(b'*')
            sock.subscribe(self.discussion.encode('ascii'))
            log.debug("bound")
            while self.valid:
                msg = await sock.recv_multipart() # waits for msg to be ready
                log.debug("got socket msg %s", msg)
                await self.on_recv(msg)
                log.debug("msg managed")
        except asyncio.CancelledError:
            console.info('cancelled')
        finally:
            console.info('closing websocket')
            sock.close()
            await self.close()

    @staticmethod
    async def sockjs_handler(msg, session):
        if msg.type == sockjs.MSG_OPEN:
            active_socket = ActiveSocket(session)
        elif msg.type == sockjs.MSG_MESSAGE:
            socket = ActiveSocket.by_session(session)
            if socket:
                await socket.on_message(msg.data)
        elif msg.type == sockjs.MSG_CLOSED:
            socket = ActiveSocket.by_session(session)
            if socket:
                await socket.close()


async def log_queue(zmq_context, out_socket):
    socket = zmq_context.socket(zmq.SUB)
    try:
        socket.connect(out_socket)
        socket.subscribe(b'')
        log.debug("log subscribed")
        while True:
            msg = await socket.recv()
            log.debug(msg)
    finally:
        socket.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("usage: python changes_router.py configuration.ini")
        exit()

    logging.config.fileConfig(sys.argv[1],)

    settings = configparser.ConfigParser({'changes_prefix': ''})
    settings.read(sys.argv[-1])


    in_socket = settings.get(SECTION, 'changes_socket')
    out_socket = settings.get(SECTION, 'changes_socket_out', fallback=in_socket + "p")
    changes_prefix = settings.get(SECTION, 'changes_prefix')
    token_secret = settings.get(SECTION, 'session.secret')
    websocket_port = settings.getint(SECTION, 'changes_websocket_port')
    # NOTE: Not sure those are always what we want.
    requires_secure = settings.getboolean(SECTION, 'require_secure_connection')
    server_protocol = 'https' if requires_secure else 'http'
    server_port = settings.getint(SECTION, 'public_port')
    if requires_secure and server_port == 80:
        # old misconfiguration
        server_port = 443
    server_host = settings.get(SECTION, 'public_hostname')
    server_url = "%s://%s:%d" % (server_protocol, server_host, server_port)

    setup_raven(settings)

    for socket_name in (in_socket, out_socket):
        if socket_name.startswith('ipc://'):
            socket_name = in_socket[6:]
            dir = dirname(socket_name)
            if not exists(dir):
                makedirs(dir)

    setup_router(in_socket, out_socket)

    for socket_name in (in_socket, out_socket):
        if socket_name.startswith('ipc://'):
            socket_name = socket_name[6:]
            for i in range(5):
                if exists(socket_name):
                    break
                sleep(0.1)
            else:
                raise RuntimeError("could not create socket " + socket_name)
            if not access(socket_name, R_OK | W_OK):
                raise RuntimeError(socket_name + " cannot be accessed")

    zmq_context, loop = setup_async_loop()
    ActiveSocket.setup(zmq_context, token_secret, server_url, out_socket)
    app = setup_app('/socket', server_url, loop)

    def term(*_ignore):
        for task in asyncio.all_tasks():
            task.cancel()
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, term)

    try:
        loop.create_task(log_queue(zmq_context, out_socket))
        web.run_app(app, port=websocket_port)
    except KeyboardInterrupt:
        term()
        raise
    except Exception:
        capture_exception()
        raise
