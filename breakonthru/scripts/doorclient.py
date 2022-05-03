import asyncio
import configparser
import gpiozero
import json
import os
import pexpect
import queue
import setproctitle
import signal
import socket
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
            relock_queue,
            broadcast_queue,
            server,
            secret,
            clientidentity,
            logger,
    ):
        self.unlock_queue = unlock_queue
        self.relock_queue = relock_queue
        self.broadcast_queue = broadcast_queue
        self.server = server
        self.secret = secret
        self.clientidentity = clientidentity
        self.logger = logger

    def log(self, msg):
        self.logger.info(f"UNLKL {msg}")

    def run(self):
        setproctitle.setproctitle("doorclient-unlocklistener")
        try:
            self.log("starting unlock listener")
            while True:
                # serve exits if doorserver is disconnected, just reestablish
                # a connection in this case via this loop
                try:
                    asyncio.run(self.serve())
                except (
                        websockets.exceptions.ConnectionClosedError,
                        websockets.exceptions.InvalidStatusCode,
                        asyncio.TimeoutError,
                        socket.gaierror
                ):
                    pass
        except KeyboardInterrupt:
            return

    async def serve(self):
        async with websockets.connect(self.server) as websocket:
            self.log("sending identification")
            await websocket.send(
                json.dumps(
                    {"type": "identification",
                     "body": self.clientidentity,
                     "secret": self.secret}
                )
            )
            lasttime = 0
            awaiting_relock = False
            while True:
                now = time.time()
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=.25
                    )
                except websockets.ConnectionClosedOK:
                    self.log("connection closed ok")
                    break
                except asyncio.TimeoutError:
                    if now > (lasttime + 30):
                        # keepalive every 30 seconds
                        lasttime = now
                        await websocket.pong()
                    try:
                        bmesg = self.broadcast_queue.get(block=False)
                    except queue.Empty:
                        pass
                    else:
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "broadcast",
                                    "body": bmesg,
                                }
                            )
                        )

                    if awaiting_relock:
                        try:
                            when, doornum = self.relock_queue.get(block=False)
                        except queue.Empty:
                            continue
                        await websocket.send(
                            json.dumps(
                                {"type": "ack",
                                 "msgid": awaiting_relock,
                                 "final": True,
                                 "body": f"relocked door {doornum}",
                                 }
                            )
                        )
                        awaiting_relock = False

                else:
                    self.log("got websocket message")
                    message = json.loads(message)
                    serverprovidedsecret = message.get('secret')
                    if serverprovidedsecret == self.secret:
                        msgtype = message.get("type")
                        if msgtype == "unlock":
                            user = message["body"]
                            msgid = message["msgid"]
                            doornum = message["doornum"]
                            character = f"unlock request by {user} for door {doornum}"
                            when = time.time()
                            self.unlock_queue.put((when, doornum))
                            self.log(f"enqueued {character}")
                            awaiting_relock = msgid
                            await websocket.send(
                                json.dumps(
                                    {
                                        "type": "ack",
                                        "msgid": msgid,
                                        "body": character,
                                    }
                                )
                            )
                            self.log("sent ack")


class UnlockExecutor:
    def __init__(
            self,
            unlock_queue,
            relock_queue,
            unlock_gpio_pins,
            door_unlocked_duration,
            logger,
    ):
        self.unlock_queue = unlock_queue
        self.relock_queue = relock_queue
        self.unlock_gpio_pins = unlock_gpio_pins
        self.door_unlocked_duration = door_unlocked_duration
        self.logger = logger

    def log(self, msg):
        self.logger.info(f"UNLKX {msg}")

    def run(self):
        setproctitle.setproctitle("doorclient-unlockexecutor")
        try:
            self._run()
        except KeyboardInterrupt:
            return

    def _run(self):
        self.log("starting unlock executor")
        self.log(f"unlock gpio pins are {self.unlock_gpio_pins}")
        last_relock_times = {}
        # gpiozero objects cannot be defined in the main process, only in subproc
        buzzers = []
        for pin in self.unlock_gpio_pins:
            buzzers.append(gpiozero.Buzzer(pin))
        while True:
            try:
                while True:
                    when, doornum = self.unlock_queue.get(timeout=.5)
                    if when > last_relock_times.get(doornum, 0):
                        break
            except queue.Empty:
                continue

            now = time.time()
            self.log(f"unlocking door {doornum}")
            buzzer = buzzers[doornum]
            try:
                buzzer.on()
                time.sleep(self.door_unlocked_duration)
            finally:
                buzzer.off()
                self.relock_queue.put((now, doornum))
                self.log(f"relocked door {doornum}")
                last_relock_times[doornum] = now


class PageListener:

    def __init__(
            self,
            page_queue,
            callbutton_gpio_pin,
            callbutton_bouncetime,
            logger,
    ):
        self.page_queue = page_queue
        self.callbutton_gpio_pin = callbutton_gpio_pin
        self.callbutton_bouncetime = callbutton_bouncetime
        self.logger = logger

    def log(self, msg):
        self.logger.info(f"PAGEL {msg}")

    def run(self):
        setproctitle.setproctitle("doorclient-pagelistener")
        # gpiozero objects cannot be defined in the main process, only in subproc
        button = gpiozero.Button(
            pin=self.callbutton_gpio_pin,
            bounce_time=self.callbutton_bouncetime / 1000.0,
        )
        try:
            self.log("starting page listener")
            self.log(f"callbutton gpio pin is {self.callbutton_gpio_pin}")

            def enqueue(*arg):
                now = time.time()
                self.logger.debug("enqueuing page")
                self.page_queue.put(now)
                self.log("enqueued page")

            button.when_pressed = enqueue
            signal.pause()
        except KeyboardInterrupt:
            pass


class PageExecutor:
    def __init__(
            self,
            page_queue,
            broadcast_queue,
            pjsua_bin,
            pjsua_config_file,
            pagingsip,
            page_throttle_duration,
            logger,
    ):
        self.page_queue = page_queue
        self.broadcast_queue = broadcast_queue
        self.pjsua_bin = pjsua_bin
        self.pjsua_config_file = pjsua_config_file
        self.pagingsip = pagingsip
        self.page_throttle_duration = page_throttle_duration
        self.logger = logger

    def log(self, msg):
        self.logger.info(f"PAGEX {msg}")

    def run(self):
        setproctitle.setproctitle("doorclient-pageexecutor")
        try:
            self._run()
        except KeyboardInterrupt:
            return

    def _run(self):
        self.log("starting page executor")

        while True:
            self.log("pjsua attempting to register with asterisk")
            try:
                cmd = f'{self.pjsua_bin} --config-file {self.pjsua_config_file}'
                self.log(f"executing {cmd}")
                self.child = pexpect.spawn(cmd, encoding='utf-8', timeout=10)
                self.child.logfile_read = sys.stdout
                self.child.expect('registration success')  # fail if not successful
                self.log("pjsua registration success")
                break
            except pexpect.exceptions.TIMEOUT:
                self.log("pjsua registration failure, retrying")
                self.child.terminate()
                continue

        last_page_time = 0

        while True:
            # see all output more quickly, for debugging
            try:
                # doesn't wait for 1000 bytes, waits for one byte if it's ready
                self.child.read_nonblocking(1000, timeout=0)
            except pexpect.exceptions.TIMEOUT:
                pass

            try:
                request = self.page_queue.get(timeout=0.5)
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
        self.broadcast_queue.put("SIP: paging all connected handsets")
        self.child.sendline('m')
        self.child.expect('Make call:')
        self.child.sendline(self.pagingsip)


unlock_queue = Queue()
relock_queue = Queue()
page_queue = Queue()
broadcast_queue = Queue()


def run_doorclient(
    server,
    secret,
    logger,
    unlock_gpio_pins,
    door_unlocked_duration,
    clientidentity,
    callbutton_gpio_pin,
    callbutton_bouncetime,
    pjsua_bin,
    pjsua_config_file,
    paging_sip,
    page_throttle_duration,
):
    procs = []

    unlock_listener = Process(
        name='unlock_listener',
        daemon=True,
        target=UnlockListener(
            unlock_queue,
            relock_queue,
            broadcast_queue,
            server,
            secret,
            clientidentity,
            logger,
        ).run
    )
    procs.append(unlock_listener)

    unlock_executor = Process(
        name='unlock_executor',
        daemon=True,
        target=UnlockExecutor(
            unlock_queue,
            relock_queue,
            unlock_gpio_pins,
            door_unlocked_duration,
            logger,
        ).run
    )
    procs.append(unlock_executor)

    page_listener = Process(
        name='page_listener',
        daemon=True,
        target=PageListener(
            page_queue,
            callbutton_gpio_pin,
            callbutton_bouncetime,
            logger,
        ).run
    )
    page_listener.start()

    page_executor = Process(
        name='page_executor',
        daemon=True,
        target=PageExecutor(
            page_queue,
            broadcast_queue,
            pjsua_bin,
            pjsua_config_file,
            paging_sip,
            page_throttle_duration,
            logger,
        ).run,
    )
    procs.append(page_executor)

    for proc in procs:
        proc.start()

    try:
        while True:
            for subproc in procs:
                if not subproc.is_alive():
                    raise AssertionError(f"subprocess {subproc} died")
                time.sleep(1)
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
    unlock_queue.put((now, 0))


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
    unlock_gpio_pins = args['unlock_gpio_pins'] = []
    unlock_gpio_pins.append(int(section.get("unlock0_gpio_pin", 26)))
    unlock_gpio_pins.append(int(section.get("unlock1_gpio_pin1", 24)))
    args['door_unlocked_duration'] = int(section.get("door_unlocked_duration", 5))
    args['clientidentity'] = section.get("clientidentity", "doorclient")
    args['callbutton_gpio_pin'] = int(section.get("callbutton_gpio_pin", 16))
    args['callbutton_bouncetime'] = int(section.get("callbutton_bouncetime", 2))
    args['page_throttle_duration'] = int(section.get("page_throttle_duration", 15))
    logger.info(f"MAIN pid is {os.getpid()}")
    run_doorclient(**args)
