import machine
import utime

from neopixel import NeoPixel

numpix = 144
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

pixel_colors = {}

for x in range(divisor):
    color = divided[x]
            
    start = (numpix//divisor) * x
    end = start + (numpix//divisor)

    for pixel in range(start, end):
        pixel_colors[pixel] = color


def segmented():
    for pixel, color in pixel_colors.items():
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
            percent = level / (65535 / 2)
            if percent > 1:
                percent -= 1
            if percent > .1: # don't register at 10% or below
                start = 0
                end = int(numpix * percent)
                leds = list(range(start, end))
                print((percent, leds))
                for x in leds:
                    strip[x] = pixel_colors[x]
                strip.write()
                utime.sleep_ms(10)
            clear()
    finally:
        strip.fill(blank)
        strip.write()

analog_audio_graph()
