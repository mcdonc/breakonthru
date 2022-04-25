import argparse
import asyncio
import configparser
import gpiozero
import json
import os
import pexpect
import queue
import socket
import signal
import sys
import time
import websockets
import websockets.exceptions

from multiprocessing import Process, Queue

from breakonthru.util import teelogger

class UnlockListener:
    def __init__(
            self,
            unlock_queue,
            server,
            secret,
            clientidentity,
            logger,
    ):
        self.unlock_queue = unlock_queue
        self.server = server
        self.secret = secret
        self.clientidentity = clientidentity
        self.logger = logger
        
    def log(self, msg):
        self.logger.info(f"UNLKL {msg}")

    def run(self):
        try:
            self.log("starting unlock listener")
            while True:
                # serve exits if doorserver is disconnected, just reestablish
                # a connection in this case via this loop
                try:
                    asyncio.run(self.serve())
                except (websockets.exceptions.ConnectionClosedError,
                        asyncio.TimeoutError, socket.gaierror):
                    pass
        except KeyboardInterrupt:
            return

    async def serve(self):
        async with websockets.connect(self.server) as websocket:
            self.log("sending identification")
            await websocket.send(
                json.dumps(
                    {"type":"identification",
                     "body":self.clientidentity,
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
                    self.log("got websocket message")
                    message = json.loads(message)
                    serverprovidedsecret = message.get('secret')
                    if serverprovidedsecret == self.secret:
                        msgtype = message.get("type")
                        if msgtype == "unlock":
                            user = message["body"]
                            self.log("enqueueing unlock request by %s" % user)
                            self.unlock_queue.put(now)


class UnlockExecutor:
    def __init__(
            self,
            unlock_queue,
            unlock_gpio_pin,
            door_unlocked_duration,
            logger,
    ):
        self.unlock_queue = unlock_queue
        self.unlock_gpio_pin = unlock_gpio_pin
        self.door_unlocked_duration = door_unlocked_duration
        self.logger = logger

    def log(self, msg):
        self.logger.info(f"UNLKX {msg}")

    def run(self):
        try:
            self._run()
        except KeyboardInterrupt:
            return

    def _run(self):
        self.log("starting unlock executor")
        self.log(f"unlock gpio pin is {self.unlock_gpio_pin}")
        last_relock_time = 0
        # gpio objects cannot be defined in the main process, only in subproc
        buzzer = gpiozero.Buzzer(self.unlock_gpio_pin)
        while True:
            try:
                while True:
                    result = self.unlock_queue.get(timeout=.5)
                    if result > last_relock_time:
                        break
            except queue.Empty:
                continue

            now = time.time()
            self.log("door unlocking")
            try:
                buzzer.on()
                time.sleep(self.door_unlocked_duration)
            finally:
                buzzer.off()
                self.log("door relocked")
                last_relock_time = now


class PageListener:
    _rising = 0
    def __init__(
            self,
            page_queue,
            callbutton_gpio_pin,
            callbutton_bouncetime,
            callbutton_holdtime,
            logger,
    ):
        self.page_queue = page_queue
        self.callbutton_gpio_pin = callbutton_gpio_pin
        self.callbutton_bouncetime = callbutton_bouncetime
        self.callbutton_holdtime = callbutton_holdtime
        self.logger = logger

    def log(self, msg):
        self.logger.info(f"PAGEL {msg}")

    def run(self):
        # gpio objects cannot be defined in the main process, only in subproc
        button = gpiozero.Button(
            pin=self.callbutton_gpio_pin,
            bounce_time=self.callbutton_bouncetime / 1000.0,
            hold_time=self.callbutton_holdtime /1000.0,
        )
        try:
            self.log("starting page listener")
            self.log(f"callbutton gpio pin is {self.callbutton_gpio_pin}")
            def enqueue(*arg):
                self.log("enqueuing page")
            button.when_held = enqueue
            while True:
                self.logger.debug(
                    f"page listener waiting for pin {self.callbutton_gpio_pin}"
                )
                time.sleep(.1)
        except KeyboardInterrupt:
            pass

class PageExecutor:
    def __init__(
            self,
            page_queue,
            pjsua_bin,
            pjsua_config_file,
            pagingsip,
            pagingduration,
            page_throttle_duration,
            drainevery,
            logger,
    ):
        self.page_queue = page_queue
        self.pjsua_bin = pjsua_bin
        self.pjsua_config_file = pjsua_config_file
        self.pagingsip = pagingsip
        self.pagingduration = pagingduration
        self.page_throttle_duration = page_throttle_duration
        self.drainevery = drainevery
        self.logger = logger

    def log(self, msg):
        self.logger.info(f"PAGEX {msg}")

    def run(self):
        try:
            self._run()
        except KeyboardInterrupt:
            return

    def _run(self):
        self.log("starting page executor")
        last_page_time = 0
        last_drain = 0

        while True:
            self.log("pjsua attempting to register with asterisk")
            try:
                cmd = f'{self.pjsua_bin} --config-file {self.pjsua_config_file}'
                self.log(f"executing {cmd}")
                self.child = pexpect.spawn(cmd, encoding='utf-8', timeout=10)
                self.child.logfile_read = sys.stdout
                self.child.expect('registration success') # fail if not successful
                self.log("pjsua registration success")
                break
            except pexpect.exceptions.TIMEOUT:
                self.log("pjsua registration failure, retrying")
                self.child.terminate()
                continue

        while True:
            now = time.time()

            # see all output more quickly, for debugging
            if self.drainevery and (now > (last_drain + self.drainevery)):
                last_drain = now
                self.child.sendline('echo ping')
                self.child.expect('>>>') # fail if it died

            try:
                request = self.page_queue.get(timeout=1)
            except queue.Empty:
                continue

            now = time.time()

            if request > (last_page_time + self.page_throttle_duration):
                last_page_time = now
                self.log("Paging")
                self.page()
            else:
                self.log(f"Throttled page request from time {request}")

    def page(self):
        child = self.child
        self.child.sendline('h')
        self.child.expect('>>>')
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

unlock_queue = Queue()
page_queue = Queue()

def run_doorclient(
    server,
    secret,
    logger,
    unlock_gpio_pin,
    door_unlocked_duration,
    clientidentity,
    callbutton_gpio_pin,
    callbutton_bouncetime,
    callbutton_holdtime,
    pjsua_bin,
    pjsua_config_file,
    paging_sip,
    paging_duration,
    drainevery,
    page_throttle_duration,
):
    procs = []

    unlock_listener = Process(
        name = 'unlock_listener',
        target=UnlockListener(
            unlock_queue,
            server,
            secret,
            clientidentity,
            logger,
        ).run
    )
    procs.append(unlock_listener)

    unlock_executor = Process(
        name = 'unlock_executor',
        target=UnlockExecutor(
            unlock_queue,
            unlock_gpio_pin,
            door_unlocked_duration,
            logger,
        ).run
    )
    procs.append(unlock_executor)

    page_listener = Process(
        name = 'page_listener',
        target=PageListener(
            page_queue,
            callbutton_gpio_pin,
            callbutton_bouncetime,
            callbutton_holdtime,
            logger,
        ).run
    )
    page_listener.start()

    page_executor = Process(
        name = 'page_executor',
        target=PageExecutor(
            page_queue,
            pjsua_bin,
            pjsua_config_file,
            paging_sip,
            paging_duration,
            page_throttle_duration,
            drainevery,
            logger,
        ).run,
    )
    procs.append(page_executor)

    [ proc.start() for proc in procs ]

    try:
        while True:
            for subproc in procs:
                if not subproc.is_alive():
                    raise AssertionError(f"subprocess {subproc} died")
                subproc.join(timeout=.1)
    except KeyboardInterrupt:
        pass
    finally:
        for subproc in procs:
            if subproc.is_alive():
                subproc.kill()

# for testing
def enqueue_page(*arg):
    now = time.time()
    page_queue.put(now)

def enqueue_unlock(*arg):
    now = time.time()
    unlock_queue.put(now)

signal.signal(signal.SIGUSR1, enqueue_unlock)
signal.signal(signal.SIGUSR2, enqueue_page)

def main():
    args = {}
    try:
        config_file = sys.argv[1]
    except IndexError:
        print("doorclient <config_file_name>")
        sys.exit(2)
    if config_file in ('-h', '--help'):
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
    loglevel = section.get("loglevel", "INFO")
    logfile = section.get("logfile")
    logger = teelogger(logfile, loglevel)
    args['logger'] = logger
    args['unlock_gpio_pin'] = int(section.get("unlock_gpio_pin", 18))
    args['door_unlocked_duration'] = int(section.get("door_unlocked_duration", 10))
    args['clientidentity'] = section.get("clientidentity", "doorclient")
    args['callbutton_gpio_pin'] = int(section.get("callbutton_gpio_pin", 16))
    args['callbutton_bouncetime'] = int(section.get("callbutton_bouncetime", 60))
    args['callbutton_holdtime'] = int(section.get("callbutton_holdtime", 250))
    args['paging_duration'] = int(section.get("paging_duration", 100))
    args['page_throttle_duration'] = int(section.get("page_throttle_duration", 30))
    args['drainevery'] = int(section.get("drainevery", 0))
    logger.info(f"MAIN pid is {os.getpid()}")
    client = run_doorclient(**args)
