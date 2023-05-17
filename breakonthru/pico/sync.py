import machine
import time

commands = [
    b"AT",
    b"AT+IPR=115200",
    b"AT+BAND=915000000",
    b"AT+NETWORKID=18"
    b"AT+ADDRESS=1",
    ]

tx_pin = machine.Pin(4)
rx_pin = machine.Pin(5)

uart = machine.UART(1, 115200, tx=tx_pin, rx=rx_pin)

for command in commands:
    uart.write(command+ b"\r\n")
    response = uart.readline().decode()
    print(response)

# send a message
msg = "HELLO"
msglen = len(msg)
recipient = 2

send = f"AT+SEND={recipient},{msglen},{msg}\r\n".encode()
uart.write(send)

while True:
    if uart.any():
        response = uart.readline().decode()
        print(response)
    time.sleep_ms(100)
        
        
