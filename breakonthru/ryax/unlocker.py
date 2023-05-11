import select
import os
import io
import time
import sys

LF = b'\n'
CR = b'\r'
CRLF = CR+LF

class UartHandler:
    def __init__(self, uart, commands=()):
        self.commands = list(commands)
        self.poller = select.poll()
        self.poller.register(uart, select.POLLIN)
        self.buffer = bytearray()
        self.uart = uart

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
                print(cmd)
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
                        print(resp)
                        #samplerecv = "+RCV=50,5,HELLO,-99,40"
                        if resp.startswith('+RCV='):
                            address, length, rest = resp[5:].split(',', 2)
                            address = int(address)
                            datalen = int(length)
                            message = rest[:datalen]
                            rssi, snr = map(int, rest[datalen+1:].split(',', 1))
                            self.handle_message(address, message, rssi, snr)
                        if resp and expect:
                            assert resp==expect, f"expected {expect}, got {resp}"
                        cmd = None
                        expect = None

def get_linux_uart():
    import termios
    import tty
    fd = os.open('/dev/ttyUSB0', os.O_NOCTTY|os.O_RDWR|os.O_NONBLOCK)
    tty.setraw(fd)
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(
        fd)
    baudrate = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW,
                      [iflag, oflag, cflag, lflag, baudrate, baudrate, cc])

    uart = io.FileIO(fd, "r+")
    #uart = io.TextIOWrapper(uart)
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
    def __init__(self, commands=()):
        uart = get_linux_uart()
        UartHandler.__init__(self, uart, commands)

    def handle_message(self, address, message, rssi, snr):
        # this is a message to unlock the door
        print(f"RECEIVED {message} from {address}")

class LinuxDoorTransmitter(UartHandler):
    def __init__(self, commands=()):
        self.last_send = 0
        uart = get_linux_uart()
        UartHandler.__init__(self, uart, commands)

    def handle_message(self, address, message, rssi, snr):
        # this is a message that the door was relocked
        print(f"RECEIVED {message} from {address}")
        if message == "79F":
            print("Door relocked")

    def handle_inputs(self):
        now = time.time()
        if now > self.last_send + 10:
            cmd = "AT+SEND=1,3,80F"
            print(f"sending {cmd}")
            self.commands.append((cmd, ''))
            self.last_send = now

class PiPicoDoorReceiver(UartHandler):
    def __init__(self, commands=(), uartid=0, baudrate=115200, tx_pin=0, rx_pin=1):
        uart = get_pipico_uart(uartid, baudrate, tx_pin, rx_pin)
        UartHandler.__init__(self, uart, commands)
        self.unlocked = None

    def handle_message(self, address, message, rssi, snr):
        # this is a message to unlock the door
        print(f"RECEIVED {message} from {address}")
        if message == "80F":
            self.unlock()

    def unlock(self):
        print("unlocking")
        self.unlocked = time.time()

    def relock(self):
        print("relocking")
        self.unlocked = None
        self.commands.append(("AT+SEND=2,3,79F", ""))

    def handle_inputs(self):
        now = time.time()
        if self.unlocked:
            if now > self.unlocked + 5:
                self.relock()

class PiPicoDoorTransmitter(UartHandler):
    def __init__(self, commands=(), uartid=0, baudrate=115200, tx_pin=0, rx_pin=1):
        uart = get_pipico_uart(uartid, baudrate, tx_pin, rx_pin)
        UartHandler.__init__(self, uart, commands)

    def handle_message(self, address, message, rssi, snr):
        # this is a message that the door was relocked
        print(f"RECEIVED {message} from {address}")

if __name__ == "__main__":
    OK = "+OK"
    commands = [
        ('AT', ''), # flush any old data pending CRLF
        ('AT+BAND=915000000', OK), # mhz band
        ('AT+NETWORKID=18', OK), # network number, shared by door/apt
        ('AT+IPR=115200', '+IPR=115200'), # baud rate
        ]
    if sys.platform == 'rp2':
        commands.append(('AT+ADDRESS=1', OK)), # network address (1: door, 2: apt)
        commands.append(('AT+MODE=2,3000,3000', OK)), # smart receive mode
        unlocker = PiPicoDoorReceiver(commands, uartid=1, tx_pin=4, rx_pin=5)
    else:
        commands.append(('AT+ADDRESS=2', OK)), # network address (1: door, 2: apt)
        unlocker = LinuxDoorTransmitter(commands)
    unlocker.runforever()
