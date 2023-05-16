
import select
import time
import machine

LF = b'\n'
CR = b'\r'
CRLF = CR+LF

class PicoDoorReceiver:
    def __init__(self, commands=(), uartid=1, baudrate=115200, tx_pin=4, rx_pin=5,
                 unlock_pin=16, unlocked_duration=5, authorized_sender=2):
        uart = machine.UART(uartid)
        uart.init(
            baudrate=baudrate, tx=machine.Pin(tx_pin), rx=machine.Pin(rx_pin)
        )
        # pop any bytes in the OS buffers before returning to avoid any state
        # left over since the last time we used the uart
        uart.read()

        self.uart = uart
        self.last_blink = 0 # used by blink method
        self.unlocked = None # used by unlock and relock methods
        self.unlocked_duration = unlocked_duration
        self.authorized_sender = authorized_sender
        self.unlock_pin = machine.Pin(unlock_pin, machine.Pin.OUT)
        self.onboard_led = machine.Pin("LED")
        self.buffer = bytearray()
        self.commands = list(commands)
        self.poller = select.poll()
        print(self.poller)
        self.poller.register(uart, select.POLLIN)
        
    def handle_message(self, address, message, rssi, snr):
        self.log(f"RECEIVED {message} from {address}")
        if message == "80F" and address == self.authorized_sender:
            # this is a message to unlock the door
            self.unlock()

    def unlock(self):
        self.log(f"Receiver unlocking using pin {self.unlock_pin}")
        self.unlocked = time.time()
        self.unlock_pin.value(1)
        self.onboard_led.value(1)

    def relock(self):
        self.log(f"Receiver relocking using pin {self.unlock_pin}")
        self.unlock_pin.value(0)
        self.onboard_led.value(0)
        self.unlocked = None
        # 79F indicates the door has relocked
        self.commands.append(("AT+SEND=2,3,79F", ""))

    def blink(self, period):
        # this turns on the led, then registers a callback to be called 10 seconds
        # in the future to turn it off
        def turnoff(t):
            self.onboard_led.value(0)
        self.onboard_led.value(1)
        t = machine.Timer()
        t.init(
            mode=machine.Timer.ONE_SHOT, period=period, callback=turnoff
        )

    def handle_inputs(self):
        now = time.time()
        if self.unlocked:
            if now >= self.unlocked + self.unlocked_duration:
                self.relock()
        if not self.unlocked and (now >= self.last_blink + 10):
            # status blink, but don't do it during unlocking
            self.blink(200)
            self.last_blink = now
    def log(self, msg):
        print(msg)

    def runforever(self):
        cmd = None
        while True:
            self.handle_inputs()
            if self.commands and cmd is None:
                cmd, expect = self.commands.pop(0)
                self.log(cmd)
                self.uart.write(cmd.encode('ascii')+CRLF)
            result = self.poller.poll(1000) # ms
            for obj, flag in result:
                if flag & select.POLLIN:
                    data = self.uart.read()
                    if data is None:
                        continue
                    data = data.replace(CR, b'')
                    self.buffer = self.buffer + data
                    while LF in self.buffer:
                        line, self.buffer = self.buffer.split(LF, 1)
                        line.strip(CR)
                        resp = line.decode('ascii', 'replace')
                        self.log(resp)
                        if resp.startswith('+RCV='):
                            # parse e.g. "+RCV=50,5,HELLO,-99,40"
                            address, length, rest = resp[5:].split(',', 2)
                            # address will be "50", length will be "5"
                            # "rest" will be "HELLO,-99,40"
                            address = int(address)
                            datalen = int(length)
                            message = rest[:datalen]
                            # message will be "HELLO"
                            rssi, snr = map(int, rest[datalen+1:].split(',', 1))
                            self.handle_message(address, message, rssi, snr)
                        if resp and expect:
                            assert resp==expect, f"expected {expect}, got {resp}"

                        cmd = None
                        expect = None


OK = "+OK"
commands = [
    ('AT', ''), # flush any old data pending CRLF
    ('AT+IPR=115200', '+IPR=115200'), # baud rate
    ('AT+BAND=915000000', OK), # mhz band
    ('AT+NETWORKID=18', OK), # network number, shared by door
    ('AT+ADDRESS=1', OK), # network address (1: door, 2: sender)
    ]
unlocker = PicoDoorReceiver(
    commands,
    unlock_pin=16,
    unlocked_duration=5,
    authorized_sender=2,
)
unlocker.runforever()
