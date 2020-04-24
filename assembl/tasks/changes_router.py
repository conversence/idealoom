"""This process obtains JSON representations of modified, created or deleted
database objects through ZeroMQ, and feeds them to browser clients
through a websocket."""
import signal
import sys
from os import makedirs, access, R_OK, W_OK
from os.path import exists, dirname
import configparser
from time import sleep
import logging
import logging.config
from functools import partial

import asyncio
from aiohttp import web, WSMsgType, ClientSession
from aiohttp.web_runner import GracefulExit
# import aiohttp_cors
import sockjs
import simplejson as json
import zmq
from zmq.asyncio import Context

# from assembl.lib.zmqlib import INTERNAL_SOCKET
from assembl.lib.raven_client import setup_raven, capture_exception
from assembl.lib.web_token import decode_token, TokenInvalid

# Inspired by socksproxy.

log = logging.getLogger("assembl.tasks.changes_router")

SECTION = 'app:idealoom'
Everyone = 'system.Everyone'
Authenticated = 'system.Authenticated'


def setup_router(in_socket, out_socket):
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    td = zmq.devices.ProcessDevice(zmq.FORWARDER, zmq.XSUB, zmq.XPUB)
    td.bind_in(in_socket)
    td.bind_out(out_socket)
    td.setsockopt_in(zmq.IDENTITY, b'XSUB')
    td.setsockopt_out(zmq.IDENTITY, b'XPUB')
    td.start()
    signal.signal(signal.SIGINT, original_sigint_handler)
    return td


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


def setup_app(path):
    app = web.Application()
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
    return app


class Dispatcher(object):

    _dispatcher = None

    @classmethod
    def get_instance(cls):
        assert cls._dispatcher
        return cls._dispatcher

    @classmethod
    def set_instance(cls, instance):
        assert cls._dispatcher is None
        cls._dispatcher = instance

    def __init__(self, app, zmq_context, token_secret,
                 server_url, out_socket_name, path):
        if self._dispatcher:
            raise RuntimeError("Singleton")
        self.zmq_context = zmq_context
        self.token_secret = token_secret
        self.server_url = server_url
        self.out_socket_name = out_socket_name
        self.active_sockets = dict()
        self.token = None
        self.discussion = None
        self.userId = None
        self.task = None
        self.is_shutdown = False
        self.app = app
        sockjs.add_endpoint(
            app, name='changes', prefix=path+"/", handler=Dispatcher.sockjs_handler)
        app.on_startup.append(Dispatcher.start_dispatcher)
        app.on_shutdown.append(Dispatcher.shutdown)
        self.set_instance(self)

    async def startup(self):
        self.http_client = ClientSession()

    def by_session(self, session):
        return self.active_sockets.get(session.id, None)

    def start_shutdown(self):
        if self.is_shutdown:
            log.warning("shutdown twice")
            return False
        self.is_shutdown = True
        return True

    async def do_shutdown(self):
        log.info("do_shutdown")
        self.is_shutdown = True
        await asyncio.gather(*[
            session.close() for session in self.active_sockets.values()])
        if self.http_client is not None:
            await self.http_client.close()
        manager = sockjs.get_manager('changes', self.app)
        await manager.clear()

    async def on_message(self, msg, session):
        # log.debug(f"on_message: {msg}")
        if msg.type == sockjs.MSG_CLOSED:
            socket = self.by_session(session)
            if socket:
                self.active_sockets.pop(socket.session.id, None)
                await socket.close()
        if self.is_shutdown:
            return
        if msg.type == sockjs.MSG_OPEN:
            self.active_sockets[session.id] = ActiveSocket(self, session)
        elif msg.type == sockjs.MSG_MESSAGE:
            socket = self.by_session(session)
            if socket:
                await socket.on_message(msg.data)

    @staticmethod
    async def sockjs_handler(msg, session):
        await Dispatcher.get_instance().on_message(msg, session)

    @staticmethod
    async def start_dispatcher(app):
        return await Dispatcher.get_instance().startup()

    @staticmethod
    async def shutdown():
        return await Dispatcher.get_instance().do_shutdown()


class ActiveSocket(object):

    def __init__(self, dispatcher, session):
        self.session = session
        self.dispatcher = dispatcher
        self.http_client = dispatcher.http_client
        self.token_secret = dispatcher.token_secret
        self.server_url = dispatcher.server_url
        self.valid = True
        self.token = None
        self.discussion = None
        self.userId = None
        self.task = None

    def on_open(self, request):
        self.valid = True
        self.closing = False

    async def on_recv(self, data):
        try:
            data = data[-1].decode('utf-8')
            if ("r:sysadmin" not in self.roles) and '@private' in data:
                jsondata = json.loads(data)
                allowed = []
                for x in jsondata:
                    if '@private' in x:
                        private = x['@private']
                        if private is not None and not self.roles.intersection(set(private)):
                            continue
                    allowed.append(x)
                if not allowed:
                    return
                data = json.dumps(allowed)
            self.session.send(data)
            log.debug('sent:'+data)
        except Exception as e:
            log.error(e)
            capture_exception()
            await self.close()

    async def close(self):
        log.info("closing")
        if not self.valid:
            return
        self.valid = False
        if self.task and not self.task.cancelled():
            self.task.cancel()
        if self.raw_token and self.discussion and self.userId != Everyone:
            async with self.http_client.post(
                    '%s/data/Discussion/%s/all_users/%d/disconnecting' % (
                        self.server_url, self.discussion, self.token['userId']
                    ), data={'token': self.raw_token}) as resp:
                await resp.text()

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
                async with self.http_client.get(
                    '%s/api/v1/discussion/%s/permissions/Conversation.R/u/%s' % (
                            self.server_url, self.discussion, self.token['userId']
                        ), headers={"Accept": "application/json"}) as resp:
                    text = await resp.text()
                log.debug(text)
                if text != 'true':
                    return
                log.info("connected")
                if self.userId == Everyone:
                    self.roles = {Everyone}
                else:
                    async with self.http_client.get(
                        '%s/api/v1/discussion/%s/roles/allfor/%s' % (
                                self.server_url, self.discussion, self.token['userId']
                            ), headers={"Accept": "application/json"}) as resp:
                        text = await resp.text()
                        self.roles = set(json.loads(text))
                        self.roles.add(Everyone)
                        self.roles.add(Authenticated)
                        self.roles.add('local:Agent/'+str(self.token['userId']))
                loop = asyncio.get_event_loop()
                self.task = loop.create_task(self.connect())
                self.session.send('[{"@type":"Connection"}]')
                if self.token and self.raw_token and self.discussion and self.userId != Everyone:
                    async with self.http_client.post(
                            '%s/data/Discussion/%s/all_users/%d/connecting' % (
                                self.server_url, self.discussion, self.token['userId']
                            ), data={'token': self.raw_token}) as resp:
                        await resp.text()
        except Exception as e:
            log.error(e)
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
            log.info('cancelled')
        finally:
            log.info('closing websocket')
            sock.close()
            await self.close()


async def log_queue(zmq_context, out_socket):
    socket = zmq_context.socket(zmq.SUB)
    try:
        socket.connect(out_socket)
        socket.subscribe(b'')
        log.debug("log subscribed")
        while True:
            msg = await socket.recv_multipart()
            log.debug(msg)
    finally:
        socket.close()


def term(router, loop, app, *_ignore):
    if Dispatcher.get_instance().start_shutdown():
        router.launcher.terminate()
        loop.create_task(Dispatcher.shutdown())
    router.join()
    signal.alarm(1)


def raise_graceful_exit():
    log.info("Graceful exit")
    # why is it so hard to stop?
    raise GracefulExit()


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

    setup_raven(settings, use_async=True)

    for socket_name in (in_socket, out_socket):
        if socket_name.startswith('ipc://'):
            socket_name = in_socket[6:]
            sdir = dirname(socket_name)
            if not exists(sdir):
                makedirs(sdir)

    zmq_context = Context()
    router = setup_router(in_socket, out_socket)

    async def check_sockets(app):
        log.info("check_sockets")
        for socket_name in (in_socket, out_socket):
            if socket_name.startswith('ipc://'):
                socket_name = socket_name[6:]
                for i in range(5):
                    if exists(socket_name):
                        break
                    sleep(0.1)
                else:
                    log.error("fail")
                    raise RuntimeError("could not create socket " + socket_name)
                if not access(socket_name, R_OK | W_OK):
                    log.error("fail")
                    raise RuntimeError(socket_name + " cannot be accessed")
        log.info("sockets are there")
        loop = asyncio.get_event_loop()
        signal.signal(signal.SIGTERM, partial(term, router, loop, app))
        signal.signal(signal.SIGINT, partial(term, router, loop, app))
        loop.add_signal_handler(signal.SIGALRM, raise_graceful_exit)
        loop.create_task(log_queue(zmq_context, out_socket))
        log.info("signals are setup")

    path = '/socket'
    app = setup_app(path)
    Dispatcher(app, zmq_context, token_secret, server_url, out_socket, path)
    assert Dispatcher.get_instance()
    app.on_startup.append(check_sockets)

    try:
        web.run_app(app, handle_signals=False, port=websocket_port)
    except asyncio.CancelledError:
        log.info("done")
    except KeyboardInterrupt:
        raise
    except Exception:
        capture_exception()
        raise
