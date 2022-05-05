import posixpath
import time

from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory
from pyramid.static import QueryStringConstantCacheBuster

from breakonthru.authentication import (
    SessionSecurityPolicy,
    parse_passwords
    )

fiveyears = 5 * 365 * 24 * 60 * 60


class PathConstantCacheBuster:
    def __init__(self, token):
        self.token = token

    def __call__(self, request, subpath, kw):
        base_subpath, ext = posixpath.splitext(subpath)
        new_subpath = base_subpath + self.token + ext
        return new_subpath, kw


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    password_file = settings["password_file"]
    with open(password_file, "r") as f:
        passwords_text = f.read()
    passwords = parse_passwords(passwords_text)
    with Configurator(settings=settings) as config:
        config.registry.settings['passwords'] = passwords
        config.include('pyramid_chameleon')
        config.add_static_view('static', 'static', cache_max_age=3600)
        config.add_cache_buster(
            'static',
            PathConstantCacheBuster(str(int(time.time())))
        )
        config.add_route('login', '/login')
        config.add_route('logout', '/logout')
        config.add_route('token', '/token')
        config.add_route('home', '/')
        policy = SessionSecurityPolicy()
        config.set_security_policy(policy)
        factory = SignedCookieSessionFactory(
            settings['secret'],
            max_age=fiveyears,
            timeout=fiveyears
        )
        config.set_session_factory(factory)
        config.scan()
    return config.make_wsgi_app()
