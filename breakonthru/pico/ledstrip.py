from neopixel import NeoPixel
import machine
import sys
import time
import utime

numpix = 32
pin = 28
strip = NeoPixel(machine.Pin(pin), numpix)

red = (255, 0, 0)
orange = (255, 50, 0)
yellow = (255, 100, 0)
green = (0, 255, 0)
blue = (0, 0, 255)
indigo = (100, 0, 90)
violet = (200, 0, 100)
blank = (0,0,0)

colors_rgb = [red, orange, yellow, green, blue, indigo, violet]

delay = 0.5

divided = {
    0: blue,
    1: green,
    2: yellow,
    3: red,
}

divisor = 4
divided_into = int(numpix / divisor)

def segmented():

    for x in range(divisor):
        color = divided[x]
            
        start = (numpix//divisor) * x
        end = start + (numpix//divisor)

        for pixel in range(start, end):
            strip[pixel] = color
    strip.write()

def clear():
    strip.fill(blank)
    strip.write()

adc = machine.ADC(machine.Pin(26, machine.Pin.IN, pull=None)) # type: ignore
digital_sensor_pin = machine.Pin(13, machine.Pin.IN, pull=None) # type: ignore

def analog_audio_graph():
    try:
        while True:
            level = adc.read_u16()
            percent = 65535 / level
            print(percent)
            start = 0
            end = int(numpix * (percent/100))
            leds = list(range(start, end))
            print(leds)
            for x in leds:
                strip[x] = yellow
            strip.write()
            utime.sleep_ms(100)
            clear()
    finally:
        strip.fill(blank)
        strip.write()

AGO = utime.time_ns()
ONE_SECOND_IN_NS = 1000000000
STRIP_STATE = False

def toggle_leds():
    global STRIP_STATE
    if STRIP_STATE is False:
        segmented()
        STRIP_STATE = True
    else:
        clear()
        STRIP_STATE = False



def snap_detected(pin):
    stop_listening_for_snaps()
    global AGO
    try:
        now = utime.time_ns()
        if now <= AGO + ONE_SECOND_IN_NS:
            return
        else:
            AGO = now
        print('detected')
        toggle_leds()
    finally:
        start_listening_for_snaps()


def start_listening_for_snaps():
    digital_sensor_pin.irq(
        trigger=machine.Pin.IRQ_RISING,
        handler=snap_detected
    )

def stop_listening_for_snaps():
    digital_sensor_pin.irq(
        trigger=machine.Pin.IRQ_RISING,
        handler=snap_detected
    )

def clapper():
    start_listening_for_snaps()
    while True:
        utime.sleep(1)

try:
    clapper()
finally:
    clear()

