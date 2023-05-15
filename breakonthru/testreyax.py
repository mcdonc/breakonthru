import logging
import time

from reyax import UartHandler

logger = logging.getLogger()

class LinuxDoorReceiver(UartHandler):
    def __init__(self, commands=(), device="/dev/ttyUSB0", baudrate=115200):
        uart = self.get_linux_uart(device, baudrate)
        UartHandler.__init__(self, uart, logger, commands)

    def handle_message(self, address, message, rssi, snr):
        # this is a message to unlock the door
        self.log(f"RECEIVED {message} from {address}")

class LinuxDoorTransmitter(UartHandler):
    def __init__(self, commands=(), device="/dev/ttyUSB0", baudrate=115200):
        self.last_send = 0
        uart = self.get_linux_uart(device, baudrate)
        UartHandler.__init__(self, uart, logger, commands)

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

def main():
    OK = "+OK"
    commands = [
        ('AT', ''), # flush any old data pending CRLF
        ('AT+BAND=915000000', OK), # mhz band
        ('AT+NETWORKID=18', OK), # network number, shared by door/apt
        ('AT+IPR=115200', '+IPR=115200'), # baud rate
        ('AT+ADDRESS=2', OK) # network address (1: door, 2: apt)
        ]
    unlocker = LinuxDoorTransmitter(commands)
    unlocker.runforever()

if __name__ == "__main__":
    main()
