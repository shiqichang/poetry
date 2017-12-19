# @author shi.qi.chang

__author__ = 'sharon'

"""url handler"""

from aiohttp import web
from www.coroweb import get, post
from www.models import User, Quote, Comment, next_id
from www.apis import Page, APIError, APIValueError, APIResourceNotFoundError, APIPermissionError
import time, re, json, logging, hashlib, asyncio
from www import config


COOKIE_NAME = 'sharonsession'
_COOKIE_KEY = config.configs.session.secret

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[a-f0-9]{40}$')


def user2cookie(user, max_age):
    """
    Generate cookie string by user
    :param user:
    :param max_age:
    :return: cookie
    """
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    res = '-'.join(L)
    return res


async def cookie2user(cookie_str):
    """
    Parse cookie and load user if cookie is valid
    :param cookie_str:
    :return: user
    """
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user == None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        sha1_s = hashlib.sha1(s.encode('utf-8')).hexdigest()
        if sha1 != sha1_s:
            logging.info('Invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.warning(e)
        return None


def text2html(text):
    logging.info(text)
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
                filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)


def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()


def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        logging.warning(e)
    if p < 1:
        p = 1
    return p


@get('/')
async def index(*, page='1'):
    page_index = get_page_index(page)
    num = await Quote.findNumber('count(id)')
    page = Page(num, page_index)
    if num == 0:
        quotes = []
    else:
        quotes = await Quote.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        '__template__': 'index.html',
        'page': page,
        'quotes': quotes
    }


@get('/signup')
def signup():
    return {
        '__template__': 'signup.html'
    }


@get('/login')
def login():
    return {
        '__template__': 'login.html'
    }


@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r


@get('/quote/{id}')
async def get_quote(id):
    quote = await Quote.find(id)
    comments = await Comment.findAll('quote_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    quote.html_content = text2html(quote.content)
    return {
        '__template__': 'quote.html',
        'quote': quote,
        'comments': comments
    }


@get('/manage')
def manage():
    return 'redirect:/manage/comments'


@get('/manage/comments')
def manage_comments(*, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page)
    }


@get('/manage/quotes')
def manage_quotes(*, page='1'):
    return {
        '__template__': 'manage_quotes.html',
        'page_index': get_page_index(page)
    }


@get('/manage/quotes/create')
def manage_create_quote():
    return {
        '__template__': 'manage_quote_edit.html',
        'id': '',
        'action': '/api/quotes'
    }


@get('/manage/quotes/edit')
def manage_edit_quote(*, id):
    return {
        '__template__': 'manage_quote_edit.html',
        'id': id,
        'action': '/api/quotes/%s' % id
    }


@get('/manage/users')
def manage_users(*, page='1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page)
    }


@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password')
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist')
    user = users[0]
    # check password:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password')
    # authemticate ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@get('/api/users')
async def api_get_users(*, page='1'):
    page_index = get_page_index(page)
    num = await User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)


@post('/api/users')
async def api_signup_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('signup:failed', 'email', 'Email is already in use')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    if name == 'sharon':
        admin = 1
    else:
        admin = 0
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), admin=admin)
    await user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@get('/api/quotes')
async def api_quotes(*, page='1'):
    page_index = get_page_index(page)
    num = await Quote.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, quotes=())
    quotes = await Quote.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, quotes=quotes)


@post('/api/quotes')
async def api_create_quote(request, *, content):
    check_admin(request)
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty')
    quote = Quote(user_id=request.__user__.id, user_name=request.__user__.name,
                  user_image=request.__user__.image, content=content.strip())
    await quote.save()
    return quote


@get('/api/quotes/{id}')
async def api_get_quote(*, id):
    quote = await Quote.find(id)
    return quote


@post('/api/quotes/{id}')
async def api_update_quote(id, request, *, content):
    check_admin(request)
    quote = await Quote.find(id)
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    quote.content = content.strip()
    await quote.update()
    return quote


@post('/api/quotes/{id}/delete')
async def api_delete_quote(id, request):
    check_admin(request)
    quote = await Quote.find(id)
    await quote.remove()
    return dict(id=id)


@get('/api/comments')
async def api_comments(*, page='1'):
    page_index = get_page_index(page)
    num = await Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)


@post('/api/quotes/{id}/comments')
async def api_create_comment(request, *, id, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please login first')
    if not content or not content.strip():
        raise APIValueError('comment', 'comment cannot be empty')
    quote = await Quote.find(id)
    if quote is None:
        raise APIResourceNotFoundError('Quote')
    comment = Comment(quote_id=quote.id, user_id=user.id, user_name=user.name,
                      user_image=user.image, content=content.strip())
    await comment.save()
    return comment


@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):
    check_admin(request)
    c = await Comment.find(id)
    if c is None:
        raise APIResourceNotFoundError('Comment')
    await c.remove()
    return dict(id=id)