from neopixel import NeoPixel
import utime
import sys
import machine

numpix = 144
pin = 16
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
blank = (0,0,0)

divided = {
    0: yellow,
    1: yellow,
    2: yellow,
    3: yellow,
}

divisor = 4
divided_into = int(numpix / divisor)

def segmented():

    for x in range(divisor):
        color = divided[x]
            
        start = (numpix//divisor) * x
        end = start + (numpix//divisor)

        for pixel in range(start, end):
            sys.stdout.write(f"{pixel} ")
            sys.stdout.write(f"{color}\n")
            strip[pixel] = color
    strip.write()

def clear():
    strip.fill(blank)
    strip.write()

audio = machine.ADC(machine.Pin(26, machine.Pin.IN))

def get_audio_level():
    level = audio.read_u16()
    return level

try:
    while True:
        level = get_audio_level()
        percent = 65535 / level
        print(percent)
        start = 0
        end = int(numpix * (percent/100))
        leds = list(range(start, end))
        print(leds)
        for x in leds:
            strip[x] = yellow
        strip.write()
        #utime.sleep_ms(100)
        clear()
finally:
    strip.fill(blank)
    strip.write()


# try:
#     segmented()
#     utime.sleep(5)
# finally:
#     clear()

#utime.sleep_ms(5000)
#strip.fill((0,0,0))
#strip.show()
#strip.fill((0,0,0))
#strip.show()
# try:
#     while True:
#         strip.set_pixel(random.randint(0, numpix-1), colors_rgb[random.randint(0, len(colors_rgb)-1)])
#         strip.set_pixel(random.randint(0, numpix-1), colors_rgb[random.randint(0, len(colors_rgb)-1)])
#         strip.set_pixel(random.randint(0, numpix-1), colors_rgb[random.randint(0, len(colors_rgb)-1)])
#         strip.set_pixel(random.randint(0, numpix-1), colors_rgb[random.randint(0, len(colors_rgb)-1)])
#         strip.set_pixel(random.randint(0, numpix-1), colors_rgb[random.randint(0, len(colors_rgb)-1)])
#         strip.show()
#         utime.sleep(delay)
#         strip.fill((0,0,0))
# finally:
#     strip.fill((0,0,0))
#     strip.show()
