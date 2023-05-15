# this module is actually imported by reyaxlinux, so it imports some
# Micropython-only modules at method scope

import select
import time

LF = b'\n'
CR = b'\r'
CRLF = CR+LF

class DumbLogger:
    def info(self, msg):
        print(msg)

class UartHandler:
    def __init__(self, uart, logger, commands=()):
        self.uart = uart
        self.logger = logger
        self.commands = list(commands)
        self.poller = select.poll()
        self.poller.register(uart, select.POLLIN)
        self.buffer = bytearray()

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

class PiPicoUartHandler(UartHandler):
    def __init__(
            self, logger, commands, uartid=0, baudrate=1152000, tx_pin=0, rx_pin=1
    ):
        # import machine only works on Pi Pico, but this module is imported by
        # reyaxlinux.py
        import machine
        tx_pin = machine.Pin(tx_pin)
        rx_pin = machine.Pin(rx_pin)
        uart = machine.UART(uartid, baudrate, tx=tx_pin, rx=rx_pin)
        # send an AT command and read any bytes in the OS buffers before returning
        # to avoid any state left over since the last time we used the uart
        uart.write(b'AT'+CRLF)
        uart.flush()
        uart.read()
        print(uart)
        UartHandler.__init__(self, uart, logger, commands)


class PiPicoDoorReceiver(PiPicoUartHandler):
    last_blink = 0
    def __init__(self, commands=(), uartid=0, baudrate=115200, tx_pin=0, rx_pin=1,
                 unlock_pin=16, unlocked_duration=5, authorized_sender=2):
        # import machine only works on Pi Pico, but this module is imported by
        # reyaxlinux.py
        import machine
        self.machine = machine
        self.unlocked_duration = unlocked_duration
        self.authorized_sender = authorized_sender
        self.unlocked = None
        self.unlock_pin = machine.Pin(unlock_pin)
        self.onboard_led = machine.Pin("LED")
        logger = DumbLogger()
        PiPicoUartHandler.__init__(
            self, logger, commands, uartid, baudrate, tx_pin, rx_pin
        )

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
        def turnoff(t):
            self.onboard_led.value(0)
        self.onboard_led.value(1)
        t = self.machine.Timer()
        t.init(
            mode=self.machine.Timer.ONE_SHOT, period=period, callback=turnoff
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

class PiPicoDoorTransmitter(PiPicoUartHandler):
    def __init__(self, commands=(), uartid=0, baudrate=115200, tx_pin=0, rx_pin=1):
        logger = DumbLogger()
        PiPicoUartHandler.__init__(
            self, logger, commands, uartid, baudrate, tx_pin, rx_pin
        )

    def handle_message(self, address, message, rssi, snr):
        # this is a message that the door was relocked
        self.log(f"RECEIVED {message} from {address}")

def main():
    OK = "+OK"
    commands = [
        ('AT', ''), # flush any old data pending CRLF
        ('AT+BAND=915000000', OK), # mhz band
        ('AT+NETWORKID=18', OK), # network number, shared by door/apt
        ('AT+IPR=115200', '+IPR=115200'), # baud rate
        ('AT+ADDRESS=1', OK), # network address (1: door, 2: apt)
        ]
    unlocker = PiPicoDoorReceiver(
        commands,
        uartid=1,
        tx_pin=4,
        rx_pin=5,
        unlock_pin=16,
        unlocked_duration=5,
        authorized_sender=2,
    )
    unlocker.runforever()

if __name__ == "__main__":
    main()
