import select
import os
import io
import time
import sys

LF = b'\n'
CR = b'\r'
CRLF = CR+LF

def get_default_logger():
    try:
        import logging
        logger = logging.getLogger()
    except ImportError:
        class DumbLogger:
            def info(self, msg):
                print(msg)
        logger = DumbLogger()
    return logger

class UartHandler:
    def __init__(self, uart, commands=(), logger=None):
        self.commands = list(commands)
        self.poller = select.poll()
        self.poller.register(uart, select.POLLIN)
        self.buffer = bytearray()
        self.uart = uart
        if logger is None:
            logger = get_default_logger()
        self.logger = logger

    def log(self, msg):
        self.logger.info(msg)

    def handle_message(self, address, message, rssi, snr):
        raise NotImplementedError

    def handle_inputs(self):
        pass

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

def get_linux_uart(device, baudrate):
    import termios
    import tty
    BAUD_MAP = {
        115200: termios.B115200,
    }
    fd = os.open(device, os.O_NOCTTY|os.O_RDWR|os.O_NONBLOCK)
    tty.setraw(fd)
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(
        fd)
    baudrate = BAUD_MAP[baudrate]
    termios.tcsetattr(fd, termios.TCSANOW,
                      [iflag, oflag, cflag, lflag, baudrate, baudrate, cc])

    uart = io.FileIO(fd, "r+")
    uart.write(b'AT'+CRLF)
    uart.flush()
    time.sleep(1)
    uart.read()
    return uart

def get_pipico_uart(uartid=0, baudrate=115200, tx_pin=0, rx_pin=1):
    import machine
    tx_pin = machine.Pin(tx_pin)
    rx_pin = machine.Pin(rx_pin)
    uart = machine.UART(uartid, baudrate, tx=tx_pin, rx=rx_pin)
    uart.write(b'AT'+CRLF)
    uart.flush()
    time.sleep(1)
    uart.read()
    return uart

class LinuxDoorReceiver(UartHandler):
    def __init__(self, commands=(), device="/dev/ttyUSB0", baudrate=115200):
        uart = get_linux_uart(device, baudrate)
        UartHandler.__init__(self, uart, commands)

    def handle_message(self, address, message, rssi, snr):
        # this is a message to unlock the door
        self.log(f"RECEIVED {message} from {address}")

class LinuxDoorTransmitter(UartHandler):
    def __init__(self, commands=(), device="/dev/ttyUSB0", baudrate=115200):
        self.last_send = 0
        uart = get_linux_uart(device, baudrate)
        UartHandler.__init__(self, uart, commands)

    def handle_message(self, address, message, rssi, snr):
        # this is a message that the door was relocked
        self.log(f"RECEIVED {message} from {address}")
        if message == "79F":
            self.log("Received door relocked confirmation")

    def handle_inputs(self):
        now = time.time()
        if now > self.last_send + 10:
            cmd = "AT+SEND=1,3,80F"
            self.log("Asking for door lock")
            self.log(f"sending {cmd}")
            self.commands.append((cmd, ''))
            self.last_send = now

class PiPicoDoorReceiver(UartHandler):
    last_blink = 0
    def __init__(self, commands=(), uartid=0, baudrate=115200, tx_pin=0, rx_pin=1,
                 unlock_pin=16, unlocked_duration=5, authorized_sender=2):
        import machine
        self.unlocked_duration = unlocked_duration
        self.authorized_sender = authorized_sender
        self.unlocked = None
        self.unlock_pin = machine.Pin(unlock_pin)
        self.onboard_led = machine.Pin("LED")
        uart = get_pipico_uart(uartid, baudrate, tx_pin, rx_pin)
        UartHandler.__init__(self, uart, commands)

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

    def handle_inputs(self):
        now = time.time()
        if self.unlocked:
            if now >= self.unlocked + self.unlocked_duration:
                self.relock()
        if now >= self.last_blink + 10:
            blink(200)
            self.last_blink = now

class PiPicoDoorTransmitter(UartHandler):
    def __init__(self, commands=(), uartid=0, baudrate=115200, tx_pin=0, rx_pin=1):
        uart = get_pipico_uart(uartid, baudrate, tx_pin, rx_pin)
        UartHandler.__init__(self, uart, commands)

    def handle_message(self, address, message, rssi, snr):
        # this is a message that the door was relocked
        self.log(f"RECEIVED {message} from {address}")

def blink(period):
    import machine
    led = machine.Pin("LED")
    def turnoff(t):
        led.value(0)
    led.value(1)
    t = machine.Timer()
    t.init(mode=machine.Timer.ONE_SHOT, period=period, callback=turnoff)

def main():
    OK = "+OK"
    commands = [
        ('AT', ''), # flush any old data pending CRLF
        ('AT+BAND=915000000', OK), # mhz band
        ('AT+NETWORKID=18', OK), # network number, shared by door/apt
        ('AT+IPR=115200', '+IPR=115200'), # baud rate
        ]
    if sys.platform == 'rp2':
        blink(5000)
        commands.append(('AT+ADDRESS=1', OK)), # network address (1: door, 2: apt)
        unlocker = PiPicoDoorReceiver(
            commands,
            uartid=1,
            tx_pin=4,
            rx_pin=5,
            unlock_pin=16,
            unlocked_duration=5,
            authorized_sender=2,
        )
    else:
        commands.append(('AT+ADDRESS=2', OK)), # network address (1: door, 2: apt)
        unlocker = LinuxDoorTransmitter(commands)
    unlocker.runforever()

if __name__ == "__main__":
    main()
