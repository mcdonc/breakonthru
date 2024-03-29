import machine
import time

commands = [
    b"AT",
    b"AT+IPR=115200",
    b"AT+BAND=915000000",
    b"AT+NETWORKID=18",
    b"AT+ADDRESS=1",
]

tx_pin = machine.Pin(4)
rx_pin = machine.Pin(5)

uart = machine.UART(1, 115200, tx=tx_pin, rx=rx_pin)


def readline(uart):
    while True:
        if uart.any():
            response = uart.readline().decode()
            return response


# do AT commands that set up our LoRa module
for command in commands:
    uart.write(command + b"\r\n")
    response = readline(uart)
    print(response)

# send a message
msg = "HELLO"
msglen = len(msg)
recipient = 2

send = f"AT+SEND={recipient},{msglen},{msg}\r\n".encode()
uart.write(send)

while True:
    response = readline(uart)
    print(response)
    time.sleep_ms(100)

# other synchronous UART examples are in
# https://www.youtube.com/watch?v=x4dZafO5FNg

# see these links for a way you can write MicroPython code that looks
# synchronous but isn't.
#
# - https://www.youtube.com/watch?v=5VLvmA__2v0&t=28s
# - https://github.com/peterhinch/micropython-async/blob/master/v3/as_demos/auart.py
# - https://github.com/peterhinch/micropython-async/blob/master/v3/as_demos/auart_hd.py
#
