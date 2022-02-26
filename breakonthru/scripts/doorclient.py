import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import websockets
import websockets.exceptions

class Doorclient:
    webrtc_client_proc = None
    comm_start_time = None
    unlocking = False
    
    def __init__(self, sink, source, webrtc_cli_path, server, secret,
                 logfile=None, echocancel=False, gpio_pin=18,
                 talk_duration=60, door_unlocked_duration=10):
        self.gpio_pin = gpio_pin
        self.talk_duration = talk_duration
        self.door_unlocked_duration = door_unlocked_duration
        if echocancel:
            os.system( "/usr/bin/pactl unload-module module-echo-cancel")
            os.system(f"/usr/bin/pactl load-module module-echo-cancel aec_method=webrtc "
                       "source_name=echocancel-source sink_name=echocancel-sink "
                       "source_master={source} sink_master={sink}")
            source = "echocancel-source"
            sink = "echocancel-sink"
        self.sink = sink
        self.source = source
        self.webrtc_cli_path = webrtc_cli_path
        self.server = server
        self.secret = secret

        logging.basicConfig(filename=logfile,
                            level=logging.INFO,
                            format='%(asctime)s %(message)s',
                            datefmt='%m/%d/%Y %I:%M:%S %p')

        logger = logging.getLogger()
        if logfile is not None:
            # tee to stdout too
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            # create formatter
            formatter = logging.Formatter(
                '%(asctime)s %(message)s',
                datefmt='%m/%d/%Y %I:%M:%S %p'
            )
            # add formatter to ch
            ch.setFormatter(formatter)
            # add ch to logger
            logger.addHandler(ch)
        self.logger = logger
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_pin, GPIO.OUT)
        
    def log(self, msg):
        self.logger.info(msg)
            
    def kill_webrtc_client_proc(self):
        if self.webrtc_client_proc is not None:
            try:
                self.webrtc_client_proc.kill()
            except:
                pass
            self.webrtc_client_proc = None
            self.comm_start_time = None

    def lock(self):
        import RPi.GPIO as GPIO
        self.log("door locking")
        try:
            GPIO.output(self.gpio_pin, 0)
        finally:
            self.unlocking = False

    def unlock(self):
        import RPi.GPIO as GPIO

        if self.unlocking:
            self.log("already unlocking, wont unlock again")
            return

        self.log("door unlocking")
        GPIO.output(self.gpio_pin, 1)
        self.unlocking = True
        loop = asyncio.get_event_loop()
        loop.call_later(self.door_unlocked_duration, self.lock)

    async def serve(self):
        webrtc_client_command = (
            self.webrtc_cli_path,
#            "--pulse-buf", "10ms",
#            "--source-frame", "10ms",
#            "--sink-frame", "10ms",
#            "--jitter-buf", "20ms",
#            "--max-drift", "20ms",
            "--answer",
            "--source", self.source,
            "--sink", self.sink
        )

        async with websockets.connect(self.server) as websocket:
            self.log("sending identification")
            await websocket.send(
                json.dumps(
                    {"type":"identification",
                     "body":"doorclient",
                     "secret":self.secret}
                )
            )
            lasttime = 0
            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=1.0
                    )
                except websockets.ConnectionClosedOK:
                    self.log("connection closed ok")
                    break
                except asyncio.TimeoutError:
                    currtime = time.time()
                    if currtime > (lasttime + 30):
                        # keepalive every 30 seconds
                        lasttime = currtime
                        await websocket.pong()
                    if self.webrtc_client_proc is not None:
                        now = time.time()
                        if now > (self.comm_start_time + self.talk_duration):
                            self.log("killing webrtc client: exceed max durat")
                            self.kill_webrtc_client_proc()
                            continue
                        while True:
                            try:
                                line = await asyncio.wait_for(
                                    self.webrtc_client_proc.stderr.readline(),
                                    timeout=0.1
                                )
                            except asyncio.TimeoutError:
                                line = ''
                            if not line:
                                break
                            line = line.decode('ascii')
                            sys.stdout.write(line)
                            sys.stdout.flush()
                            if line.startswith(
                                (
                                "ICE connection state changed to disconnected",
                                "ICE connection state changed to failed",
                                "ICE connection state changed to closed",
                                )
                            ):
                                self.log("killing webrtc client process: disco")
                                self.kill_webrtc_client_proc()
                                break
                else:
                    self.log("got message")
                    message = json.loads(message)
                    serverprovidedsecret = message.get('secret')
                    if serverprovidedsecret == self.secret:
                        msgtype = message.get("type")
                        if msgtype == "offer":
                            offer = message["body"]
                            if self.webrtc_client_proc is not None:
                                self.kill_webrtc_client_proc()
                                self.log("starting client proc when one existed")
                            self.comm_start_time = time.time()
                            self.log(" ".join(webrtc_client_command))
                            proc = await asyncio.create_subprocess_exec(
                                *webrtc_client_command,
                                stdin=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                            )
                            self.webrtc_client_proc = proc
                            self.log("writing offer to stdin of webrtc-client")
                            proc.stdin.write(offer.encode('ascii'))
                            proc.stdin.close()
                            self.log("wrote offer to stdin of webrtc-client")

                            answer = ""

                            while True:
                                line = await proc.stdout.readline()
                                if not line:
                                    break
                                answer = answer + line.decode('ascii')
                            self.log("sending answer\n-----\n%s\n-----" % answer)
                            await websocket.send(
                                json.dumps(
                                    {"type":'answer',
                                     "body":answer,
                                     "secret":self.secret}
                                )
                            )
                            self.log("sent answer")

                        if msgtype == "unlock":
                            user = message["body"]
                            self.log("unlocking door by request of %s" % user)
                            self.unlock()

    def run(self):
        try:
            while True:
                try:
                    asyncio.run(self.serve())
                except (websockets.exceptions.ConnectionClosedError,
                        websockets.exceptions.InvalidStatusCode,
                        asyncio.exceptions.TimeoutError,
                        OSError):
                    self.kill_webrtc_client_proc()
                    time.sleep(3)
        finally:
            self.kill_webrtc_client_proc()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sink', help='Pulseaudio sink name', required=True)
    parser.add_argument('--source', help='Pulseaudio source name', required=True)
    parser.add_argument('--webrtc-cli', help='Path to webrtc-cli binary',
                        required=True)
    parser.add_argument('--secret',
                        help="payload secret between doorserver/client",
                        required=True)
    parser.add_argument('--server', help="url to remote WS server",
                        required=True)
    parser.add_argument('--logfile', default=None)
    parser.add_argument('--echocancel', dest='echocancel',
                        help="Use Pulse echo cancellation",
                        action='store_true')
    parser.add_argument('--gpio-pin', help="door unlock gpio signal pin num",
                        type=int, default=18)
    parser.add_argument('--talk-duration', help="Duration to leave comms open",
                        type=int, default=60)
    parser.add_argument('--door-unlock-duration',
                        help="Duration to leave door unlocked",
                        type=int, default=18)
    parser.set_defaults(echocancel=False)
    args = parser.parse_args()
    client = Doorclient(
        args.sink,
        args.source,
        args.webrtc_cli,
        args.server,
        args.secret,
        args.logfile,
        args.echocancel,
        args.gpio_pin,
        args.talk_duration,
        args.door_unlock_duration
    )
    client.run()
    
            
