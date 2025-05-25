import argparse
import asyncio
import configparser
import json
import os
import pprint
import sys
import time
import uuid
import websockets
import websockets.exceptions

from breakonthru.authentication import parse_passwords, make_token
from breakonthru.util import teelogger


class Doorserver:
    unlockdata = None

    def __init__(self, secret, password_file, doors_file, logger):
        self.secret = secret
        with open(password_file, "r") as f:
            passwords = f.read()
        self.passwords = parse_passwords(passwords)
        self.logger = logger
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
            except (
                websockets.ConnectionClosedOK,
                websockets.exceptions.ConnectionClosedError,
            ):
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
                        wids = broadcast["wids"]
                        if wsid not in wids:
                            await websocket.send(
                                json.dumps(broadcast["message"])
                            )
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
                    userdata = self.passwords.get(user)
                    if userdata is not None:
                        password = userdata.get("password")
                        if password is not None:
                            expectedtoken = make_token(self.secret, password)
                            if expectedtoken == token:
                                identification = ident
                                self.log("identification is %s" % ident)
                                continue
                    self.log("bad identification for %s (%s)" % (ident, user))

            if identification == "webclient":
                if msgtype == "unlock":
                    self.log(
                        f"unlock request received from webclient {pprint.pformat(message)}"
                    )
                    # we must send the secret to the doorclient
                    user = message["body"]
                    msgid = uuid.uuid4().hex
                    userdata = self.passwords.get(user)
                    doornum = message["doornum"]
                    if userdata is not None:
                        if int(doornum) in userdata["doors"]:
                            unlockdata = {
                                "type": "unlock",
                                "body": user,
                                "doornum": doornum,
                                "msgid": msgid,
                                "secret": self.secret,
                            }
                            self.unlockdata = json.dumps(unlockdata)
                            self.pending_acks[msgid] = wsid
                        else:
                            self.log(
                                f"unauthorized doornum {doornum} unlock requested "
                                f"by {user}"
                            )

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
    args = {}
    try:
        config_file = sys.argv[1]
    except IndexError:
        print("doorserver <config_file_name>")
        sys.exit(2)
    if config_file in ("-h", "--help"):
        print("doorserver <config_file_name>")
        sys.exit(2)

    config = configparser.ConfigParser()
    config.read(config_file)
    section = config["doorserver"]

    password_file = os.environ.get("DOORSERVER_PASSWORD_FILE")
    if password_file is None:
        password_file = section.get("password_file")
        if password_file is None:
            raise AssertionError("password_file must be supplied")
    args["password_file"] = password_file

    doors_file = os.environ.get("DOORSERVER_DOORS_FILE")
    if doors_file is None:
        doors_file = section.get("doors_file")
        if doors_file is None:
            raise AssertionError("doors_file must be supplied")
    args["doors_file"] = doors_file

    secret = os.environ.get("DOORSERVER_WSSECRET")
    if secret is None:
        secret = section.get("secret")
        if secret is None:
            raise AssertionError("secret must be supplied")
    args["secret"] = secret

    loglevel = section.get("loglevel", "INFO")
    logfile = section.get("logfile")
    logger = teelogger(logfile, loglevel)
    args["logger"] = logger
    logger.info(f"MAIN pid is {os.getpid()}")
    server = Doorserver(**args)
    try:
        server.run()
    except KeyboardInterrupt:
        pass
