import bcrypt
import json
import requests

from websocket import create_connection

from pyramid.httpexceptions import HTTPSeeOther
from pyramid.security import remember, forget
from pyramid.view import view_config, forbidden_view_config, notfound_view_config

from breakonthru.authentication import refresh_token


@forbidden_view_config(
    renderer='breakonthru:templates/403.pt'
)
def forbidden_view(request):
    request.response.status = 403
    return {}


@notfound_view_config(
    renderer='breakonthru:templates/404.pt'
)
def notfound_view(request):
    request.response.status = 404
    return {}


@view_config(
    route_name='login'
)
def login_view(request):
    headers = {}
    username = request.params.get('username')
    password = request.params.get('password')
    if username is not None:
        username = username.lower()
    userdata = request.registry.settings['passwords'].get(username)
    if userdata is not None:
        storedhashbytes = userdata["password"].encode('utf-8')
        passbytes = password.encode('utf-8')
        if bcrypt.checkpw(passbytes, storedhashbytes):
            headers = remember(request, username)
    return HTTPSeeOther(location='/', headers=headers)


@view_config(
    route_name='logout',
)
def logout_view(request):
    headers = forget(request)
    request.session.pop("token", None)
    return HTTPSeeOther(location='/', headers=headers)


@view_config(
    route_name='home',
    renderer='breakonthru:templates/index.pt',
    permission='view'
)
def index_view(request):
    username = request.authenticated_userid
    userdata = request.registry.settings['passwords'].get(username)
    allowed_doors = userdata["doors"]
    all_doors = request.registry.settings['doors']
    doors = []
    for n, door in enumerate(all_doors):
        if n in allowed_doors:
            doors.append(door)
    return {
        "websocket_url": request.registry.settings['websocket_url'],
        "doorsip": request.registry.settings['doorsip'],
        "allowed_doors": allowed_doors,
        "doors":doors,
    }


@view_config(
    route_name='token',
    renderer='json',
    permission='view',
    )
def token_view(request):
    user = request.authenticated_userid
    token = refresh_token(request, user)
    return {"token": token, "user": user}


@view_config(
    route_name='directunlock'
)
def directunlock_view(request):
    reqdata = {}
    reqdata['username'] = request.params['username']
    reqdata['password'] = request.params['password']
    doornum = int(request.params['doornum'])
    login_url = request.host_url + '/login'
    token_url = request.host_url + '/token'
    session = requests.Session()
    with session:
        session.post(login_url, data=reqdata)
        r = session.get(token_url)
        tokendata = json.loads(r.content)
    identificationdata = {
        "type":"identification",
        "body":"webclient",
        "user":tokendata["user"],
        "token":tokendata["token"],
        }
    unlockdata = {
        "type": "unlock",
        "body": tokendata['user'],
        "doornum":doornum,
    }
    websocket_url = request.registry.settings['websocket_url']
    ws = create_connection(websocket_url)
    ws.send(json.dumps(identificationdata))
    ws.send(json.dumps(unlockdata))
    response = request.response
    response.body = 'OK'
    response.content_type = 'text/plain'
    return response
