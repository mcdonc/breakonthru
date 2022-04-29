from cryptacular.bcrypt import BCRYPTPasswordManager

from pyramid.httpexceptions import HTTPSeeOther
from pyramid.security import remember, forget
from pyramid.view import view_config
from pyramid.view import forbidden_view_config
from pyramid.view import notfound_view_config

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
    storedhash = request.registry.settings['passwords'].get(username)
    if not (None in (storedhash, username, password)):
        manager = BCRYPTPasswordManager()
        if manager.check(storedhash, password):
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
    return {
        "websocket_url": request.registry.settings['websocket_url'],
        "doorsip": request.registry.settings['doorsip'],
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
