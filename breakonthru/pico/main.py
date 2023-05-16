import select
import time
import machine

LF = b"\n"
CR = b"\r"
CRLF = CR+LF

class PicoDoorReceiver:
    def __init__(
            self, commands=(), uartid=1, baudrate=115200, tx_pin=4, rx_pin=5,
            unlock_pin=16, unlocked_duration=5, authorized_sender=2,
            watchdog=None,
    ):
        uart = machine.UART(uartid)
        uart.init(
            baudrate=baudrate, tx=machine.Pin(tx_pin), rx=machine.Pin(rx_pin)
        )
        # pop any bytes in the OS read buffers before returning to avoid any
        # state left over since the last time we used the uart; this is
        # nonblocking if there are no bytes to be read
        uart.read()

        self.uart = uart
        self.last_blink = 0 # used by blink method
        self.unlocked = False # used by unlock and relock methods
        self.unlocked_duration = unlocked_duration
        self.onboard_led = machine.Pin("LED")
        self.authorized_sender = authorized_sender
        self.watchdog = watchdog
        self.unlock_pin = machine.Pin(unlock_pin, machine.Pin.OUT)
        self.buffer = bytearray()
        self.commands = list(commands) # make a copy, dont mutate the original
        self.poller = select.poll()
        self.poller.register(uart, select.POLLIN)
        
    def handle_message(self, address, message, rssi, snr):
        self.log(f"RECEIVED {message} from {address}")
        if message == "80F" and address == self.authorized_sender:
            # this is a message to unlock the door
            self.unlock()

    def unlock(self):
        self.log(f"Receiver unlocking using pin {self.unlock_pin}")
        self.unlocked = time.time()
        self.unlock_pin.on()
        self.onboard_led.on()

    def relock(self):
        self.log(f"Receiver relocking using pin {self.unlock_pin}")
        self.unlock_pin.off()
        self.onboard_led.off()
        self.unlocked = False
        # send back "79F" to the sender indicating that the door has been
        # relocked
        self.commands.append((f"AT+SEND={self.authorized_sender},3,79F", ""))

    def blink(self):
        # This turns on the onboard LED, then registers a callback to be called
        # 200 milliseconds in the future to turn it off.  We could blink the LED
        # more efficiently using a periodic timer, but the point is to be able
        # to know that the software is still running by looking for blinks of
        # the LED.
        self.onboard_led.on()
        self.last_blink = self.now

        def turnoff(t):
            self.onboard_led.off()

        t = machine.Timer()
        t.init(
            mode=machine.Timer.ONE_SHOT, period=200, callback=turnoff
        )

    def manage_state(self):
        # This method is called continually by runforever (during normal
        # operations, every second or so).

        self.watchdog.feed() # feed the watchdog timer to avoid board reboot

        self.now = time.time()

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
        # initialize some variables we use later
        cmd = None
        expect = None

        while True:
            # continually call manage_state to maybe relock and maybe blink led
            self.manage_state()

            if self.commands and cmd is None:
                # if there are any commands in our command list and we aren't
                # already processing a command
                cmd, expect = self.commands.pop(0)
                self.log(cmd)
                self.uart.write(cmd.encode("ascii")+CRLF)

            result = self.poller.poll(1000) # wait 1 sec for any data (1000ms)

            for obj, flag in result:
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
                        line = line.strip(CR) # strip carriage returns
                        resp = line.decode("ascii", "replace") # bytes to text
                        self.log(resp)

                        if resp.startswith("+RCV="):
                            # this is a message from the sender e.g.
                            # "+RCV=50,5,HELLO,-99,40"
                            address, length, rest = resp[5:].split(",", 2)
                            # address will be "50", length will be "5"
                            # "rest" will be "HELLO,-99,40"
                            address = int(address)
                            datalen = int(length)
                            message = rest[:datalen] # message will be "HELLO"
                            # the remaining values in the message are rssi
                            # and snr
                            rssi, snr = [
                                int(x) for x in rest[datalen+1:].split(",", 1)
                            ]
                            # call handle_message to process the message
                            self.handle_message(address, message, rssi, snr)

                        elif resp and expect:
                            # if we were expecting a response to a command,
                            # compare the response against the expected value
                            # and raise an AssertionError if it's not the
                            # same
                            if resp != expect:
                                msg = f"expect {repr(expect)},got {repr(resp)}"
                                raise AssertionError(msg)

                        # we have finished processing a command
                        cmd = None
                        expect = None


OK = "+OK"
commands = [
    ("AT", ""), # flush any old data left in the UART pending CRLF
    ("AT+IPR=115200", "+IPR=115200"), # baud rate
    ("AT+BAND=915000000", OK), # mhz band
    ("AT+NETWORKID=18", OK), # network number, shared by door
    ("AT+ADDRESS=1", OK), # network address (1: door, 2: sender)
    ]

# reboot the board if we dont feed the dog every 5 seconds
watchdog = machine.WDT(timeout=5000)

unlocker = PicoDoorReceiver(
    commands,
    unlock_pin=16,
    unlocked_duration=5,
    authorized_sender=2,
    watchdog=watchdog,
)

unlocker.runforever()
