import ryax
import time

rx = ryax.receiver()
tx = ryax.transmitter()

while True:
    tx.sendmsg(1, "BUZZ802")
    time.sleep(1)
    print(rx.receive())
