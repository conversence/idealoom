import sys
import configparser
import logging
import logging.config

from aiohttp import web
from aiocache import Cache
from aiocache.lock import RedLock

from pyoembed import oEmbed

SECTION = 'app:idealoom'

log = logging.getLogger("assembl.tasks.oembed")

cache = None


async def cached_oembed(url, maxwidth, maxheight):
    global cache
    key = ";".join((url, maxheight or "", maxwidth or ""))
    async with RedLock(cache, key, lease=5):  # Calls will wait here
        result = await cache.get(key)
        if result is not None:
            return result
        try:
            result = await oEmbed(url, maxwidth, maxheight)
        except Exception:
            result = {}
        await cache.set(key, result)
        return result


async def oembed_handler(request):
    url = request.query.get('url', None)
    if not url:
        raise web.HTTPBadRequest(body="Please give a URL")
    maxheight = request.query.get('height', None)
    maxwidth = request.query.get('width', None)
    extra = {
        "Access-Control-Allow-Origin": "*"
    }
    try:
        data = await cached_oembed(url, maxwidth=maxwidth, maxheight=maxheight)
        return web.json_response(data, headers=extra)
    except Exception:
        return web.json_response({}, headers=extra)


def make_app(argv, path=None, cache_type='MEMORY'):
    global cache
    path = path or '/oembed'
    cache_type = getattr(Cache, cache_type)
    cache = Cache(cache_type)
    app = web.Application()
    app.add_routes([web.get(path, oembed_handler)])
    return app


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("usage: python changes_router.py configuration.ini")
        exit()

    logging.config.fileConfig(sys.argv[1],)
    settings = configparser.ConfigParser({'oembed_prefix': ''})
    settings.read(sys.argv[-1])
    prefix = settings.get(SECTION, 'oembed_prefix', fallback='/oembed')
    cache_type = settings.get(SECTION, 'oembed_cache_type', fallback='MEMORY')
    app = make_app(None, prefix, cache_type)
    web.run_app(app, port=int(settings.get(SECTION, 'oembed_port')))
