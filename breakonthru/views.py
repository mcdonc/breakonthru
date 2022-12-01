from cryptacular.bcrypt import BCRYPTPasswordManager

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
        storedhash = userdata["password"]
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
