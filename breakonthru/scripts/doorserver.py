import argparse
import asyncio
import websockets
import websockets.exceptions
import json
import logging

from breakonthru.authentication import parse_passwords, make_token

class Doorserver:
    unlockdata = None

    def __init__(self, secret, password_file, logfile=None):
        self.secret = secret
        with open(password_file, "r") as f:
            passwords = f.read()
        self.passwords = parse_passwords(passwords)
        logging.basicConfig(filename=logfile,
                            level=logging.INFO,
                            format='%(asctime)s %(message)s',
                            datefmt='%m/%d/%Y %I:%M:%S %p')
        logger = logging.getLogger()
        if logfile is not None:
            # tee to stdout too
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s %(message)s',
                datefmt='%m/%d/%Y %I:%M:%S %p'
            )
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        self.logger = logger

    def log(self, msg):
        self.logger.info(msg)

    def run(self):
        asyncio.run(self.serve())

    async def serve(self):
        async with websockets.serve(self.handler, "", 8001):
            await asyncio.Future()  # run forever

    async def handler(self, websocket):
        self.log("handler kicked off with websocket %s" % websocket)
        identification = None # identification is per-connection
        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
            except (websockets.ConnectionClosedOK,
                    websockets.exceptions.ConnectionClosedError):
                break
            except asyncio.TimeoutError:
                if identification == "doorclient":
                    if self.unlockdata is not None:
                        self.log("sending unlock request")
                        await websocket.send(self.unlockdata)
                        self.log("sent unlock request")
                        self.unlockdata = None

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
                    unlockdata = {
                        "type":"unlock",
                        "body":user,
                        "secret":self.secret,
                    }
                    self.unlockdata = json.dumps(unlockdata)

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
    server.run()
