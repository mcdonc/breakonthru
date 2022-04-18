import argparse
import asyncio
import json
import os
import time
import websockets
import websockets.exceptions

from breakonthru.util import teelogger

class Doorclient:
    unlocking = False
    
    def __init__(
            self,
            server,
            secret,
            logfile=None,
            unlock_gpio_pin=18,
            door_unlocked_duration=10,
            callbutton_gpio_pin=16,
    ):
        self.server = server
        self.secret = secret
        self.door_unlocked_duration = door_unlocked_duration
        self.unlock_gpio_pin = unlock_gpio_pin
        self.callbutton_gpio_pin = callbutton_gpio_pin
        self.logger = teelogger(logfile)

    def page(self, _):
        now = time.time()
        try:
            pagerlockfile = open('/tmp/pager.lock', 'r')
        except IOError:
            self.log('skipped page, no /tmp/pager.lock file')
            return

        try:
            strpid = pagerlockfile.read()
            pagerpid = int(strpid)
        except ValueError:
            self.log(f'skipped page, garbage in lockfile: {strpid}')
            return

        self.log(f'paging, sending USR1 to {pagerpid}')
        os.system(f'kill -USR1 {pagerpid}')

    def log(self, msg):
        self.logger.info(msg)
            
    def lock(self):
        import RPi.GPIO as GPIO
        self.log("door locking")
        try:
            GPIO.output(self.unlock_gpio_pin, 0)
        finally:
            self.unlocking = False

    def unlock(self):
        import RPi.GPIO as GPIO

        if self.unlocking:
            self.log("already unlocking, wont unlock again")
            return

        self.log("door unlocking")
        GPIO.output(self.unlock_gpio_pin, 1)
        self.unlocking = True
        loop = asyncio.get_event_loop()
        loop.call_later(self.door_unlocked_duration, self.lock)

    async def serve(self):
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
                else:
                    self.log("got message")
                    message = json.loads(message)
                    serverprovidedsecret = message.get('secret')
                    if serverprovidedsecret == self.secret:
                        msgtype = message.get("type")
                        if msgtype == "unlock":
                            user = message["body"]
                            self.log("unlocking door by request of %s" % user)
                            self.unlock()

    def run(self):
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.unlock_gpio_pin, GPIO.OUT)
        GPIO.setup(self.callbutton_gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(self.callbutton_gpio_pin, GPIO.FALLING, 
                              callback=self.page, bouncetime=100)
        try:
            while True:
                asyncio.run(self.serve())
        except KeyboardInterrupt:
            pass
        finally:
            GPIO.cleanup()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--secret',
        help="payload secret between doorserver/client",
        required=True
    )
    parser.add_argument(
        '--server',
        help="url to remote WS server",
        required=True
    )
    parser.add_argument(
        '--logfile',
        default=None
    )
    parser.add_argument(
        '--door-unlock-duration',
        help="Duration to leave door unlocked",
        type=int,
        default=10
    )
    parser.add_argument(
        '--unlock-gpio-pin',
        help="door unlock gpio output pin num",
        type=int,
        default=18
    )
    parser.add_argument(
        '--callbutton-gpio-pin',
        help="callbutton gpio input pin num",
        type=int,
        default=16
    )
    args = parser.parse_args()
    client = Doorclient(
        args.server,
        args.secret,
        args.logfile,
        args.unlock_gpio_pin,
        args.door_unlock_duration,
        args.callbutton_gpio_pin,
    )
    client.run()
