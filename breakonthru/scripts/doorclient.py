import asyncio
import configparser
import gpiozero
import io
import json
import os
import pexpect
import queue
import select
import setproctitle
import signal
import socket
import sys
import termios
import time
import tty
import websockets
import websockets.exceptions

from multiprocessing import Process, Queue

from breakonthru.util import teelogger

LF = b"\n"
CR = b"\r"
CRLF = CR + LF


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
                    socket.gaierror,
                ):
                    pass
        except KeyboardInterrupt:
            return

    async def serve(self):
        async with websockets.connect(self.server) as websocket:
            self.log("sending identification")
            await websocket.send(
                json.dumps(
                    {
                        "type": "identification",
                        "body": self.clientidentity,
                        "secret": self.secret,
                    }
                )
            )
            lasttime = 0
            awaiting_relock = {}
            while True:
                now = time.time()
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(), timeout=0.25
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
                        relock_msgid = awaiting_relock.pop(doornum, None)
                        if relock_msgid is None:
                            continue
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "ack",
                                    "msgid": relock_msgid,
                                    "final": True,
                                    "body": f"relocked door {doornum}",
                                }
                            )
                        )

                else:
                    self.log("got websocket message")
                    message = json.loads(message)
                    serverprovidedsecret = message.get("secret")
                    if serverprovidedsecret == self.secret:
                        msgtype = message.get("type")
                        if msgtype == "unlock":
                            user = message["body"]
                            msgid = message["msgid"]
                            doornum = message["doornum"]
                            character = (
                                f"unlock request by {user} for "
                                f"door {doornum}"
                            )
                            when = time.time()
                            self.unlock_queue.put((when, doornum))
                            self.log(f"enqueued {character}")
                            awaiting_relock[doornum] = msgid
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


class ReyaxBuzzer:
    def __init__(self, address, reyax_queue):
        self.address = address
        self.reyax_queue = reyax_queue

    def on(self):
        self.reyax_queue.put(self.address)

    def off(self):
        pass


class UnlockExecutor:
    def __init__(
        self,
        unlock_queue,
        relock_queue,
        reyax_queue,
        unlock_gpio_pins,
        door_unlocked_duration,
        logger,
    ):
        self.unlock_queue = unlock_queue
        self.relock_queue = relock_queue
        self.reyax_queue = reyax_queue
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
        # gpiozero objects cannot be defined in the main process, only in
        # subproc
        buzzers = []
        for pin in self.unlock_gpio_pins:
            if pin.startswith("reyax:"):
                address = int(pin[6:])
                buzzers.append(ReyaxBuzzer(address, self.reyax_queue))
            else:
                buzzers.append(gpiozero.Buzzer(int(pin)))
        while True:
            try:
                while True:
                    when, doornum = self.unlock_queue.get(timeout=0.5)
                    if when > last_relock_times.get(doornum, 0):
                        break
            except queue.Empty:
                continue

            now = time.time()
            self.log(f"unlocking door {doornum}")
            buzzer = buzzers[doornum]
            try:
                buzzer.on()
                self.log(
                    f"waiting {self.door_unlocked_duration} before relocking"
                )
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
        # gpiozero objects cannot be defined in the main process, only in
        # subproc
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

        for i in range(0, 9):
            self.log(
                f"pjsua attempting to register with asterisk, try number {i}"
            )
            try:
                cmd = f"{self.pjsua_bin} --config-file {self.pjsua_config_file}"
                self.log(f"executing {cmd}")
                self.child = pexpect.spawn(cmd, encoding="utf-8", timeout=10)
                self.child.logfile_read = sys.stdout
                # fail if not successful
                self.child.expect("registration success")
                self.log("pjsua registration success")
                break
            except pexpect.exceptions.TIMEOUT:
                self.log("pjsua registration failure, retrying")
                self.child.terminate()
                continue
        else:  # nobreak
            raise AssertionError("could not register with SIP provider")

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

            if request > (last_page_time + self.page_throttle_duration):
                last_page_time = time.time()
                self.log("Paging")
                self.page()
            else:
                self.log(f"Throttled page request from time {request}")

    def page(self):
        self.broadcast_queue.put("SIP: paging all connected handsets")
        self.child.sendline("m")
        self.child.expect("Make call:")
        self.child.sendline(self.pagingsip)


class ReyaxDoorTransmitter:
    def __init__(
        self,
        logger,
        reyax_queue,
        commands=(),
        device="/dev/ttyUSB0",
        baudrate=115200,
        unlock_msg="UNLOCK",
    ):
        self.commands = list(commands)
        self.logger = logger
        self.reyax_queue = reyax_queue
        self.pending_commands = commands
        self.unlock_msg = unlock_msg

        BAUD_MAP = {
            115200: termios.B115200,
        }
        fd = os.open(device, os.O_NOCTTY | os.O_RDWR | os.O_NONBLOCK)
        tty.setraw(fd)
        iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd)
        baudrate = BAUD_MAP[baudrate]
        termios.tcsetattr(
            fd,
            termios.TCSANOW,
            [iflag, oflag, cflag, lflag, baudrate, baudrate, cc],
        )

        uart = io.FileIO(fd, "r+")
        # pop any bytes in the OS read buffers before returning to avoid any
        # state left over since the last time we used the uart; this is
        # nonblocking if there are no bytes to be read
        uart.flush()
        uart.read()

        self.uart = uart
        self.buffer = bytearray()
        self.pending_commands = list(commands)  # dont mutate the original
        self.poller = select.poll()
        self.poller.register(uart, select.POLLIN)

    def log(self, msg):
        self.logger.info(f"REYXTR {msg}")

    def handle_message(self, address, message, rssi, snr):
        self.log(f"RECEIVED {message} from {address}")

    def manage_state(self):
        try:
            address = self.reyax_queue.get(block=False)
        except queue.Empty:
            return
        msglen = len(self.unlock_msg)
        cmd = f"AT+SEND={address},{msglen},{self.unlock_msg}"
        self.log(f"sending {cmd} to {address}")
        self.commands.append((cmd, ""))

    def runforever(self):
        # initialize some variables we use later
        current_cmd = None
        expect = None

        while True:
            # continually call manage_state to maybe relock and maybe blink led
            self.manage_state()

            if self.pending_commands and current_cmd is None:
                # if there are any commands in our command list and we aren't
                # already processing a command, pop the first command
                # from the command list and send it to the Reyax
                current_cmd, expect = self.pending_commands.pop(0)
                self.log(current_cmd)
                # current_cmd is a string, but the UART expects bytes, so
                # we need to encode it to a bytes object
                current_cmd_bytes = current_cmd.encode()
                self.uart.write(current_cmd_bytes + CRLF)

            events = self.poller.poll(1000)  # wait 1 sec for any data (1000ms)
            for obj, flag in events:
                if flag & select.POLLIN:
                    # There is data available to be read on our UART.
                    # Continually add any data read from the UART to our buffer
                    data = self.uart.read()
                    self.buffer = self.buffer + data

                    # process whatever's in the buffer
                    while LF in self.buffer:
                        # We consider any data between two linefeeds to be a
                        # response
                        line, self.buffer = self.buffer.split(LF, 1)
                        line = line.strip(CR)  # strip any trailing carriage rtn
                        resp = line.decode("ascii", "replace")  # bytes to text
                        self.log(resp)

                        if resp.startswith("+RCV="):
                            # Usually we get a response to one of our own AT
                            # commands when we process a full line, but this is
                            # not one of those.  Instead, it is a message from
                            # the sender e.g.  "+RCV=50,5,HELLO,-99,40"
                            # (although in practice this is probably a door
                            # unlock request, and the message would not be
                            # "HELLO")

                            address, length, rest = resp[5:].split(",", 2)

                            # address will be "50", length will be "5"
                            # "rest" will be "HELLO,-99,40"

                            address = int(address)
                            datalen = int(length)
                            message = rest[:datalen]  # message will be "HELLO"

                            # call handle_message to process the message
                            self.handle_message(address, message)

                        elif resp and expect:
                            # if we were expecting a response to a command,
                            # compare the response against the expected value
                            # and raise an AssertionError if it's not the
                            # same
                            if resp != expect:
                                msg = f"expect {repr(expect)},got {repr(resp)}"
                                raise AssertionError(msg)

                        # we have finished processing a command
                        current_cmd = None
                        expect = None


class ReyaxTransmissionHandler:
    def __init__(self, reyax_config, reyax_queue, logger):
        self.reyax_config = reyax_config
        self.reyax_queue = reyax_queue
        self.logger = logger

    def log(self, msg):
        self.logger.info(f"REYXTH {msg}")

    def run(self):
        setproctitle.setproctitle("reyax-transmission-handler")
        try:
            self._run()
        except KeyboardInterrupt:
            return

    def _run(self):
        self.log("starting reyax transmitter")
        cfg = self.reyax_config
        self.log(f"reyax config is {cfg}")
        OK = "+OK"
        commands = [
            ("AT", ""),  # flush any old data pending CRLF
            (f'AT+BAND={cfg["band"]}', OK),  # mhz band
            (f'AT+NETWORKID={cfg["networkid"]}', OK),  # network number, shared
            (
                f'AT+IPR={cfg["baudrate"]}',
                f'+IPR={cfg["baudrate"]}',
            ),  # baudrate
            (f'AT+ADDRESS={cfg["address"]}', OK),
        ]
        tx = ReyaxDoorTransmitter(
            self.logger,
            self.reyax_queue,
            commands=commands,
            device=cfg["tty"],
            baudrate=cfg["baudrate"],
            unlock_msg=cfg["unlock_msg"],
        )
        tx.runforever()


unlock_queue = Queue()
relock_queue = Queue()
page_queue = Queue()
broadcast_queue = Queue()
reyax_queue = Queue()


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
    reyax_config,
):
    procs = []

    unlock_listener = Process(
        name="unlock_listener",
        daemon=True,
        target=UnlockListener(
            unlock_queue,
            relock_queue,
            broadcast_queue,
            server,
            secret,
            clientidentity,
            logger,
        ).run,
    )
    procs.append(unlock_listener)

    unlock_executor = Process(
        name="unlock_executor",
        daemon=True,
        target=UnlockExecutor(
            unlock_queue,
            relock_queue,
            reyax_queue,
            unlock_gpio_pins,
            door_unlocked_duration,
            logger,
        ).run,
    )
    procs.append(unlock_executor)

    page_listener = Process(
        name="page_listener",
        daemon=True,
        target=PageListener(
            page_queue,
            callbutton_gpio_pin,
            callbutton_bouncetime,
            logger,
        ).run,
    )
    page_listener.start()

    page_executor = Process(
        name="page_executor",
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

    for pin in unlock_gpio_pins:
        if pin.startswith("reyax:"):
            reyax_handler = Process(
                name="reyax_handler",
                daemon=True,
                target=ReyaxTransmissionHandler(
                    reyax_config,
                    reyax_queue,
                    logger,
                ).run,
            )
            procs.append(reyax_handler)
            break

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
def enqueue_unlock_front(*arg):
    now = time.time()
    unlock_queue.put((now, 0))


def enqueue_unlock_inner(*arg):
    now = time.time()
    unlock_queue.put((now, 1))


def enqueue_page(*arg):
    now = time.time()
    page_queue.put(now)


signal.signal(signal.SIGUSR1, enqueue_unlock_front)
signal.signal(signal.SIGUSR2, enqueue_unlock_inner)
signal.signal(signal.SIGALRM, enqueue_page)


def main():
    args = {}
    try:
        config_file = sys.argv[1]
    except IndexError:
        print("doorclient <config_file_name>")
        sys.exit(2)
    if config_file in ("-h", "--help"):
        print("doorclient <config_file_name>")
        sys.exit(2)

    config = configparser.ConfigParser()
    config.read(config_file)
    section = config["doorclient"]
    server = section.get("server")
    if server is None:
        raise AssertionError("server must be supplied")
    args["server"] = server
    secret = section.get("secret")
    if secret is None:
        raise AssertionError("secret must be supplied")
    args["secret"] = secret
    pjsua_bin = section.get("pjsua_bin")
    if pjsua_bin is None:
        raise AssertionError("pjsua_bin must be supplied")
    args["pjsua_bin"] = pjsua_bin
    pjsua_config_file = section.get("pjsua_config_file")
    if pjsua_config_file is None:
        raise AssertionError("pjsua_config_file must be supplied")
    args["pjsua_config_file"] = pjsua_config_file
    args["paging_sip"] = section.get("paging_sip", "sip:7000@127.0.0.1:5065")
    loglevel = section.get("loglevel", "INFO")
    logfile = section.get("logfile")
    logger = teelogger(logfile, loglevel)
    args["logger"] = logger
    unlock_gpio_pins = args["unlock_gpio_pins"] = []
    default_pins = ["26", "24", "13"]
    for x in range(0, 3):
        val = section.get(f"unlock{x}_gpio_pin", default_pins[x])
        unlock_gpio_pins.append(val)
    args["door_unlocked_duration"] = int(
        section.get("door_unlocked_duration", 5)
    )
    args["clientidentity"] = section.get("clientidentity", "doorclient")
    args["callbutton_gpio_pin"] = int(section.get("callbutton_gpio_pin", 16))
    args["callbutton_bouncetime"] = int(section.get("callbutton_bouncetime", 2))
    args["page_throttle_duration"] = int(
        section.get("page_throttle_duration", 15)
    )
    args["reyax_config"] = reyax = {}
    reyax["networkid"] = int(section.get("reyax_networkid", 18))
    reyax["address"] = int(section.get("reyax_address", 2))
    reyax["band"] = int(section.get("reyax_band", 915000000))
    reyax["baudrate"] = int(section.get("reyax_baudrate", 115200))
    reyax["tty"] = section.get("reyax_tty", "/dev/ttyUSB0")
    reyax["unlock_msg"] = section.get("reyax_unlock_msg", "UNLOCK")
    logger.info(f"MAIN pid is {os.getpid()}")
    run_doorclient(**args)
