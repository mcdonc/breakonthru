from machine import Pin
import time
import ryax

def test_receiver():
    relay = Pin(16, Pin.OUT, Pin.PULL_UP)
    led=Pin("LED", Pin.OUT)
    relay.value(0)
    led.value(0)
    rx = ryax.receiver()
    while True:
        if rx.uart.any():
            data = rx.receive()
            print(data)
            if 'BUZZ' in data:
                print("relay buzz")
                led.value(1)
                relay.value(1)
                time.sleep(10)
                led.value(0)
                relay.value(0)
        time.sleep_ms(500)
        
test_receiver()

 


 

         

