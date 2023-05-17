import machine
import time

commands = [
    "AT",
    "AT+IPR=115200",
    "AT+BAND=915000000",
    "AT+NETWORKID=18"
    "AT+ADDRESS=1",
    ]

tx_pin = machine.Pin(4)
rx_pin = machine.Pin(5)

uart = machine.UART(1, 115200, tx=tx_pin, rx=rx_pin)

for command in commands:
    uart.write(command+ "\r\n")
    response = uart.readline()
    print(response)

# send a message
msg = "HELLO"
msglen = len(msg)
recipient = 2

uart.write(f"AT+SEND={recipient},{msglen},{msg}\r\n")

while True:
    if uart.any():
        response = uart.readline()
        print(response)
    time.sleep_ms(100)
        
        
