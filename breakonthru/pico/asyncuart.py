import select
import time
import machine

LF = b"\n"
CR = b"\r"
CRLF = CR + LF


class PicoDoorReceiver:
    def __init__(
        self,
        commands=(),
        uartid=1,
        baudrate=115200,
        tx_pin=4,
        rx_pin=5,
        unlock_pin=16,
        unlocked_duration=5,
        authorized_sender=2,
        unlock_message="UNLOCK",
        relocked_message="RELOCKED",
        watchdog=False,
    ):
        uart = machine.UART(uartid)
        uart.init(
            baudrate=baudrate, tx=machine.Pin(tx_pin), rx=machine.Pin(rx_pin)
        )
        # pop any bytes in the OS readbuffer before returning to avoid
        # any state left over since the last time we used the uart; note that
        # read is nonblocking if there are no bytes to be read
        uart.read()

        self.uart = uart
        self.last_blink = 0  # used by blink method
        self.unlocked = False  # used by unlock and relock methods
        self.unlocked_duration = unlocked_duration  # seconds
        self.authorized_sender = authorized_sender  # LoRa address of sender
        self.unlock_message = unlock_message  # message body sent by sender
        self.relocked_message = relocked_message  # message body in response
        self.onboard_led = machine.Pin("LED")
        self.unlock_pin = machine.Pin(unlock_pin, machine.Pin.OUT)
        self.buffer = bytearray()
        self.pending_commands = list(commands)  # dont mutate the original
        self.poller = select.poll()
        self.poller.register(uart, select.POLLIN)

        if watchdog:
            # set up a watchdog timer that will restart the Pico if not fed
            # at least every five seconds
            self.watchdog = machine.WDT(timeout=5000)  # ms
        else:
            self.watchdog = None

    def handle_message(self, address, message):
        self.log(f"RECEIVED {message} from {address}")
        if message == self.unlock_message and address == self.authorized_sender:
            # this is a message to unlock the door, and it came from
            # the network address we deem authorized
            self.unlock()

    def unlock(self):
        self.log(f"Receiver unlocking using {self.unlock_pin}")
        self.unlocked = time.time()
        self.unlock_pin.on()
        self.onboard_led.on()

    def relock(self):
        self.log(f"Receiver relocking using {self.unlock_pin}")
        self.unlock_pin.off()
        self.onboard_led.off()
        self.unlocked = False
        # send a message back to the sender indicating that the door has been
        # relocked
        msg = self.relocked_message
        msglen = len(msg)
        self.pending_commands.append(
            (f"AT+SEND={self.authorized_sender},{msglen},{msg}", "")
        )

    def blink(self):
        # This turns on the onboard LED, then registers a callback to be called
        # 200 milliseconds in the future to turn it off.  We could blink the LED
        # more efficiently using a periodic timer, but the point is to be able
        # to know that the mainloop is still running by looking for blinks of
        # the LED.
        self.onboard_led.on()
        self.last_blink = self.now

        def turnoff(t):
            self.onboard_led.off()

        t = machine.Timer()
        t.init(mode=machine.Timer.ONE_SHOT, period=200, callback=turnoff)

    def startup_blink(self):
        # this will block for half a second, but it's only called at program
        # startup.
        for x in range(5):
            self.onboard_led.on()
            time.sleep_ms(100)
            self.onboard_led.off()
            time.sleep_ms(100)

    def manage_state(self):
        # This method is called continually by runforever (during normal
        # operations, every second or so).

        # feed the watchdog timer so we aren't rebooted
        if self.watchdog is not None:
            self.watchdog.feed()

        # self.now is used in other methods that this one calls. Note that its
        # value is max 1-second precision, unlike "normal" Python, which has a
        # float component.
        self.now = time.time()

        # self.log(f"Managing state at time {self.now}")

        if self.unlocked:
            # the door is currently unlocked
            if self.now >= (self.unlocked + self.unlocked_duration):
                # the unlock duration has passed, relock the door
                self.relock()
        else:
            # the door is not currently unlocked
            if self.now >= (self.last_blink + 10):
                # The last time we blinked the led was more than ten seconds
                # ago, blink again
                self.blink()

    def log(self, msg):
        print(msg)

    def runforever(self):
        # do a startup blink once
        self.startup_blink()

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


OK = "+OK"

commands = [
    ("AT", ""),  # last command in UART writebuffer might not be finalized
    ("AT+IPR=115200", "+IPR=115200"),  # baud rate
    ("AT+BAND=915000000", OK),  # mhz band
    ("AT+NETWORKID=18", OK),  # network number, shared by door
    ("AT+ADDRESS=1", OK),  # network address (1: ours, 2: sender)
]

unlocker = PicoDoorReceiver(commands)
unlocker.runforever()
