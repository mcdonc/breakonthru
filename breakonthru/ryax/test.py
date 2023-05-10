import ryax
import time

def test_transmitter():
    tx = ryax.transmitter()
    while True:
        tx.sendmsg(1, "BUZZ")
        time.sleep(5)

def test_receiver():
    rx = ryax.receiver()
    while True:
        if rx.uart.any():
            print(rx.receive())
        time.sleep_ms(100)
