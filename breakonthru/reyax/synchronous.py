import machine
import time


class Reyax:
    def __init__(self, uartid=0, baudrate=115200, tx_pin=0, rx_pin=1):
        tx_pin = machine.Pin(tx_pin)
        rx_pin = machine.Pin(rx_pin)
        self.uart = machine.UART(uartid, baudrate, tx=tx_pin, rx=rx_pin)

    def sendmsg(self, address, msg):
        msglen = len(msg)
        return self.atcommand(f'AT+SEND={address},{msglen},{msg}')

    def receive(self, numbytes=-1):
        if numbytes==-1:
            for x in range(0, 10):
                if self.uart.any():
                    break
        result = self.uart.read(numbytes)
        if result is None:
            result = b''
        result = result.decode('ascii', 'replace')
        return result

    def atcommand(self, cmd, expect="+OK\r\n"):
        self.uart.write(f'{cmd}\r\n')
        self.uart.flush()
        if expect == '':
            numbytes = -1
        else:
            numbytes = len(expect)
        time.sleep_ms(200)
        result = self.receive(numbytes)
        print({"result":result, "expect":expect, "cmd":cmd})
        if expect:
            assert result == expect, result
        return result


def receiver():
    while True:
        try:
            rx = Reyax(uartid=1, tx_pin=4, rx_pin=5)
            rx.atcommand('AT', '') # get rid of stray bytes hanging around
        except UnicodeError: # first time failure
            continue
        else:
            break

    rx.atcommand('AT') # test
    rx.atcommand('AT+BAND=915000000') # mhz band
    rx.atcommand('AT+NETWORKID=18') # network number, shared by door/apt
    rx.atcommand('AT+ADDRESS=1') # network address (1: door, 2: apt)
    rx.atcommand('AT+IPR=115200', '+IPR=115200\r\n\n') # baud rate
    #ryax.atcommand('AT+MODE=2,3000,3000') # smart power mode
    return rx


def transmitter():
    while True:
        try:
            tx = Reyax()
            tx.atcommand('AT', '') # get rid of stray bytes hanging around
        except UnicodeError: # first time failure
            continue
        else:
            break
    tx.atcommand('AT') # test
    tx.atcommand('AT+BAND=915000000') # mhz band
    tx.atcommand('AT+NETWORKID=18') # network number, shared by door/apt
    tx.atcommand('AT+ADDRESS=2') # network address (1: door, 2: apt)
    tx.atcommand('AT+IPR=115200', '+IPR=115200\r\n\n') # baud rate
    #ryax.atcommand('AT+MODE=2,3000,3000') # smart power mode
    return tx
