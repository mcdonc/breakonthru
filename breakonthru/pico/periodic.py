import machine
import time

led = machine.Pin("LED")
led.off()


def blink(t):
    print("blinking")
    led.off()
    time.sleep_ms(200)
    led.on()
    time.sleep_ms(200)


t = machine.Timer(mode=machine.Timer.PERIODIC, freq=1, callback=blink)

raise Exception("exc")
