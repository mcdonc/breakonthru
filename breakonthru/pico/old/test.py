from .synchronous import transmitter, receiver
import time


def test_transmitter():
    tx = transmitter()
    while True:
        tx.sendmsg(1, "BUZZ")
        time.sleep(5)


def test_receiver():
    rx = receiver()
    while True:
        if rx.uart.any():
            print(rx.receive())
        time.sleep_ms(100)
