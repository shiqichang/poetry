# @author shi.qi.chang
"""asynchronous web application"""
import asyncio
from aiohttp import web
import os, time, json
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import logging; logging.basicConfig(level=logging.INFO)
from www.coroweb import add_routes, add_static, manage_static
from www.handlers import cookie2user, COOKIE_NAME
from www.orm import create_pool


async def auth_factory(app, handler):
    async def auth(request):
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        return await handler(request)
    return auth


async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...%s %s' % (handler, request))
        r = await handler(request)
        logging.info('Response %s' % r)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: dir(o)).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                r['__user__'] = request.__user__
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response


def init_jinja2(app, **kw):
    logging.info('init jinja2...%s' % kw)
    options = dict(
        autoescape=kw.get('autoescape', True),
        block_start_string=kw.get('block_start_string', '{%'),
        block_end_string=kw.get('block_end_string', '%}'),
        variable_start_string=kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
        auto_reload=kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 templates path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


async def init(loop):
    await create_pool(loop, host='localhost', user='sharon',
                      password='0828715.Cxy', db='poetry')
    app = web.Application(loop=loop, middlewares=[auth_factory, response_factory])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    manage_static(app)
    srv = await loop.create_server(app.make_handler(), 'localhost', 8888)
    logging.info('server started at http://127.0.0.1:8888...')
    return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()