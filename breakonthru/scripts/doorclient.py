import argparse
import asyncio
import configparser
import json
import os
import pexpect
from queue import Empty
import sys
import time
import websockets
import websockets.exceptions

from multiprocessing import Process, Queue

from breakonthru.util import teelogger

class Doorclient:
    def __init__(
            self,
            server,
            secret,
            logfile,
            unlock_gpio_pin,
            door_unlocked_duration,
            callbutton_gpio_pin,
            callbutton_bouncetime,
            pjsua_bin,
            pjsua_config_file,
            paging_sip,
            paging_duration,
            drainevery,
            page_throttle_duration,
            ):

        unlock_queue = Queue()
        page_queue = Queue()

        unlock_listener = Process(
            target=UnlockListener(
                unlock_queue,
                server,
                secret,
                logfile,
            ).run
        )
        unlock_listener.start()

        unlock_executor = Process(
            target=UnlockExecutor(
                unlock_queue,
                unlock_gpio_pin,
                door_unlocked_duration,
                logfile,
            ).run
        )
        unlock_executor.start()
        
        page_listener = Process(
            target=PageListener(
                page_queue,
                callbutton_gpio_pin,
                callbutton_bouncetime,
                logfile,
            ).run
        )
        page_listener.start()

        page_executor = Process(
            target=PageExecutor(
                page_queue,
                pjsua_bin,
                pjsua_config_file,
                paging_sip,
                paging_duration,
                page_throttle_duration,
                drainevery,
                logfile,
            ).run,
        )
        page_executor.start()

        unlock_listener.join()
        unlock_executor.join()
        page_listener.join()
        page_executor.join()


class UnlockListener:
    def __init__(self, queue, server, secret, logfile):
        self.queue = queue
        self.server = server
        self.secret = secret
        self.logger = teelogger(logfile)
        
    def log(self, msg):
        self.logger.info(msg)

    def run(self):
        while True:
            # serve exits if doorserver is disconnected, just reestablish
            # a connection in this case via this loop
            asyncio.run(self.serve())

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
                now = time.time()
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=1.0
                    )
                except websockets.ConnectionClosedOK:
                    self.log("connection closed ok")
                    break
                except asyncio.TimeoutError:
                    if now > (lasttime + 30):
                        # keepalive every 30 seconds
                        lasttime = now
                        await websocket.pong()
                else:
                    self.log("got message")
                    message = json.loads(message)
                    serverprovidedsecret = message.get('secret')
                    if serverprovidedsecret == self.secret:
                        msgtype = message.get("type")
                        if msgtype == "unlock":
                            user = message["body"]
                            self.log("received unlock request by %s" % user)
                            self.queue.put(now)


class UnlockExecutor:
    def __init__(self, queue, unlock_gpio_pin, door_unlocked_duration, logfile):
        self.queue = queue
        self.unlock_gpio_pin = unlock_gpio_pin
        self.door_unlocked_duration = door_unlocked_duration
        self.logger = teelogger(logfile)

    def log(self, msg):
        self.logger.info(msg)

    def run(self):
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.unlock_gpio_pin, GPIO.OUT)
        last_unlock_time = 0
        while True:
            try:
                while True:
                    result = self.queue.get(timeout=.5)
                    if result > last_unlock_time:
                        break
            except Empty:
                continue

            self.log("door unlocking")
            now = time.time()
            try:
                GPIO.output(self.unlock_gpio_pin, 1)
                time.sleep(self.door_unlocked_duration)
            finally:
                GPIO.output(self.unlock_gpio_pin, 0)
                self.log("door relocked")
                last_unlock_time = now


class PageListener:
    def __init__(
            self,
            queue, 
            callbutton_gpio_pin,
            callbutton_bouncetime,
            logfile,
            ):
        self.queue = Queue
        self.callbutton_gpio_pin = callbutton_gpio_pin
        self.callbutton_bouncetime = callbutton_bouncetime
        self.logger = teelogger(logfile)

    def log(self, msg):
        self.logger.info(msg)

    def enqueue_page(self, _):
        now = time.time()
        self.queue.put(now)

    def run(self):
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False) # squash RuntimeWarning: This channel is already in use
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.callbutton_gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(
            self.callbutton_gpio_pin,
            GPIO.FALLING, 
            callback=self.enqueue_page,
            bouncetime=self.callbutton_bouncetime
        )


class PageExecutor:
    def __init__(
            self,
            queue,
            pjsua_bin,
            pjsua_config_file,
            pagingsip,
            pagingduration,
            page_throttle_duration,
            drainevery,
            logfile,
    ):
        self.queue = queue
        self.pjsua_bin = pjsua_bin
        self.pjsua_config_file = pjsua_config_file
        self.pagingsip = pagingsip
        self.pagingduration = pagingduration
        self.page_throttle_duration = page_throttle_duration
        self.drainevery = drainevery
        self.logger = teelogger(logfile)

    def log(self, msg):
        self.logger.info(msg)

    def run(self):
        last_page_time = 0
        last_drain = 0

        self.child = pexpect.spawn(
            f'{self.pjsua_bin} --config-file {self.pjsua_config_file}',
            encoding='utf-8',
            timeout=2,
        )
        self.child.logfile_read = sys.stdout
        self.child.expect('registration success') # fail if not successful

        while True:
            now = time.time()
            if self.drainevery: # see all output more quickly, for debugging
                if now > (last_drain + self.drainevery):
                    last_drain = now
                    self.child.sendline('echo 1')
                    self.child.expect('>>>') # fail if it died

            try:
                while True:
                    result = self.queue.get(timeout=.5)
                    if result > last_page_time:
                        break
            except Empty:
                continue

            self.log("Page requested")
            self.pagerequested = False
            if now > (last_page_time + self.page_throttle_duration):
                self.log("Paging")
                self.page()
            else:
                self.log("Skipping page due to throttle duration")

    def page(self):
        child = self.child
        self.hangup()
        child.sendline('m')
        child.expect('Make call:')
        child.sendline(self.pagingsip)
        i = child.expect(['CONFIRMED', 'DISCONN', pexpect.EOF, pexpect.TIMEOUT])
        now = time.time()
        if i == 0: # CONFIRMED, call ringing
            while True: # wait til the duration is over to hang up
                i = child.expect(['DISCONN', pexpect.EOF, pexpect.TIMEOUT])
                if i != 2: # if it's disconnected or program crashed
                    break
                if time.time() >= (now + self.pagingduration):
                    break
            self.child.sendline('h')
            self.child.expect('>>>')

def main():
    args = {}
    try:
        config_file = sys.argv[1]
    except IndexError:
        print("doorclient <config_file_name>")
        sys.exit(2)
    config = configparser.ConfigParser()
    config.read(config_file)
    section = config['doorclient']
    server = section.get("server")
    if server is None:
        raise AssertionError('server must be supplied')
    args['server'] = server
    secret = section.get("secret")
    if secret is None:
        raise AssertionError('secret must be supplied')
    args['secret'] = secret
    pjsua_bin = section.get("pjsua_bin")
    if pjsua_bin is None:
        raise AssertionError('pjsua_bin must be supplied')
    args['pjsua_bin'] = pjsua_bin
    pjsua_config_file = section.get("pjsua_config_file")
    if pjsua_config_file is None:
        raise AssertionError('pjsua_config_file must be supplied')
    args['pjsua_config_file'] = pjsua_config_file
    args['paging_sip'] = section.get("paging_sip", "sip:7000@127.0.0.1:5065")
    args['logfile'] = section.get("logfile")
    args['unlock_gpio_pin'] = int(section.get("unlock_gpio_pin", 18))
    args['door_unlocked_duration'] = int(section.get("door_unlocked_duration", 10))
    args['callbutton_gpio_pin'] = int(section.get("callbutton_gpio_pin", 16))
    args['callbutton_bouncetime'] = int(section.get("callbutton_bouncetime", 60))
    args['paging_duration'] = int(section.get("paging_duration", 100))
    args['page_throttle_duration'] = int(section.get("page_throttle_duration", 30))
    args['drainevery'] = int(section.get("drainevery", 0))
    client = Doorclient(**args)
    client.run()
