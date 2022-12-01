import hmac
import math
import time

from pyramid.authentication import SessionAuthenticationHelper
from pyramid.security import Allowed, Denied


class SessionSecurityPolicy:
    def __init__(self):
        self.helper = SessionAuthenticationHelper()

    def identity(self, request):
        userid = self.helper.authenticated_userid(request)
        if userid is None:
            return None
        return {'userid': userid}

    def authenticated_userid(self, request):
        """ Return a string ID for the user. """
        identity = self.identity(request)
        if identity is None:
            return None
        return str(identity['userid'])

    def permits(self, request, context, permission):
        """ Allow access to everything if signed in. """
        identity = self.identity(request)
        if identity is not None:
            return Allowed('User is signed in.')
        else:
            return Denied('User is not signed in.')

    def remember(self, request, userid, **kw):
        return self.helper.remember(request, userid, **kw)

    def forget(self, request, **kw):
        return self.helper.forget(request, **kw)


def parse_passwords(text):
    passwords = {}
    entries = text.splitlines()
    for line in entries:
        line = line.strip()
        if not ('=' in line):
            continue
        if line.startswith("#"):
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        try:
            password, doors = [x.strip() for x in value.split(":",1) ]
            doors = [ int(x) for x in doors ]
        except ValueError:
            password = value.strip()
            doors = list(range(100)) # all doors
        passwords[name] = {"password":password, "doors":doors}
    return passwords

def parse_doors(text):
    doors = []
    entries = text.splitlines()
    for line in entries:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        doors.append(line)
    return doors

def timeslice(period, currtime):
    low = int(math.floor(currtime)) - period + 1
    high = int(math.ceil(currtime)) + 1
    for x in range(low, high):
        if x % period == 0:
            return x


token_valid_secs = 60


def make_token(secret, password, valid_secs=token_valid_secs):
    now = time.time()
    slice = timeslice(valid_secs, now)
    timed = password.encode("utf-8") + str(slice).encode("ascii")
    return hmac.new(
        secret.encode("utf-8"),
        timed,
        'sha512_256'
    ).hexdigest()


def refresh_token(request, username, valid_secs=token_valid_secs):
    storedhash = request.registry.settings['passwords'].get(username.lower())
    oldtoken = request.session.get("token")
    secret = request.registry.settings["secret"]
    newtoken = make_token(secret, storedhash, valid_secs)
    if oldtoken != newtoken:
        request.session["token"] = newtoken
    return newtoken
