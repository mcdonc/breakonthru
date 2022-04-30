import argparse
import asyncio
import websockets
import websockets.exceptions
import json
import time
import uuid

from breakonthru.authentication import parse_passwords, make_token
from breakonthru.util import teelogger


class Doorserver:
    unlockdata = None

    def __init__(self, secret, password_file, logfile=None):
        self.secret = secret
        with open(password_file, "r") as f:
            passwords = f.read()
        self.passwords = parse_passwords(passwords)
        self.logger = teelogger(logfile)
        self.acks = {}
        self.pending_acks = {}
        self.broadcasts = []

    def log(self, msg):
        self.logger.info(msg)

    def run(self):
        asyncio.run(self.serve())

    async def serve(self):
        async with websockets.serve(self.handler, "", 8001):
            await asyncio.Future()  # run forever

    async def handler(self, websocket):
        self.log("handler kicked off with websocket %s" % websocket)
        wsid = websocket.id
        identification = None  # identification is per-connection
        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=0.25)
            except (websockets.ConnectionClosedOK,
                    websockets.exceptions.ConnectionClosedError):
                break
            except asyncio.TimeoutError:
                now = time.time()
                for (i, broadcast) in enumerate(self.broadcasts[:]):
                    if now - broadcast["when"] > 30:
                        del self.broadcasts[i]
                if identification == "doorclient":
                    if self.unlockdata is not None:
                        self.log("sending unlock request")
                        await websocket.send(self.unlockdata)
                        self.log("sent unlock request")
                        self.unlockdata = None
                if identification == "webclient":
                    acklist = self.acks.pop(wsid, [])
                    for ack in acklist:
                        await websocket.send(ack)
                    for broadcast in self.broadcasts:
                        wids = broadcast['wids']
                        if wsid not in wids:
                            await websocket.send(json.dumps(broadcast['message']))
                            wids.append(wsid)

                continue

            message = json.loads(message)
            msgtype = message.get("type")

            if msgtype == "identification":
                ident = message["body"]
                if ident == "doorclient":
                    clientprovidedsecret = message.get("secret")
                    if clientprovidedsecret == self.secret:
                        identification = ident
                        self.log("identification is %s" % ident)
                        continue
                    self.log("bad identification for %s" % ident)
                if ident == "webclient":
                    user = message["user"]
                    token = message["token"]
                    password = self.passwords.get(user)
                    if password is not None:
                        expectedtoken = make_token(self.secret, password)
                        if expectedtoken == token:
                            identification = ident
                            self.log("identification is %s" % ident)
                            continue
                    self.log("bad identification for %s (%s)" % (ident, user))

            if identification == "webclient":
                if msgtype == "unlock":
                    # we must send the secret to the doorclient
                    user = message["body"]
                    msgid = uuid.uuid4().hex
                    unlockdata = {
                        "type": "unlock",
                        "body": user,
                        "msgid": msgid,
                        "secret": self.secret,
                    }
                    self.unlockdata = json.dumps(unlockdata)
                    self.pending_acks[msgid] = wsid
            if identification == "doorclient":
                if msgtype == "ack":
                    msgid = message["msgid"]
                    final = message.get("final")
                    if final:
                        wsid = self.pending_acks.pop(msgid, None)
                    else:
                        wsid = self.pending_acks.get(msgid, None)
                    if wsid is not None:
                        acklist = self.acks.setdefault(wsid, [])
                        acklist.append(json.dumps(message))
                if msgtype == "broadcast":
                    self.broadcasts.append(
                        {
                            "wids": [],
                            "when": time.time(),
                            "message": message,
                        }
                    )


def main():
    global passwords
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--secret', help="payload secret between doorserver/client",
        required=True)
    parser.add_argument(
        '--passwords', help="path to password file",
        required=True)
    parser.add_argument('--logfile', default=None)
    args = parser.parse_args()
    server = Doorserver(args.secret, args.passwords, args.logfile)
    try:
        server.run()
    except KeyboardInterrupt:
        pass
