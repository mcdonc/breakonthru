import machine
import random
import utime

LEDS = {
    "A": machine.Pin(9,machine.Pin.OUT),
    "B": machine.Pin(3,machine.Pin.OUT),
    "C": machine.Pin(5,machine.Pin.OUT),
    "D": machine.Pin(6,machine.Pin.OUT),
    "E": machine.Pin(7,machine.Pin.OUT),
    "F": machine.Pin(2,machine.Pin.OUT),
    "G": machine.Pin(8,machine.Pin.OUT),
    "DP": machine.Pin(4,machine.Pin.OUT),
    }

order = [ "G", "F", "A", "B", "G", "E", "D", "C" ]

DIGITS = {
    0: ("A", "B", "C", "D", "E", "F"),
    1: ("B", "C"),
    2: ("A", "B", "G", "E", "D"),
    3: ("A", "B", "G", "C", "D"),
    4: ("B", "G", "C", "F"),
    5: ("A", "F", "G", "C", "D"),
    6: ("A", "F", "E", "D", "C", "G"),
    7: ("A", "B", "C"),
    8: ("A", "B", "C", "D", "E", "G", "F"),
    9: ("A", "B", "C", "G", "F"),
}

def clear():
    for name, pin in LEDS.items():
        pin.off()

def display_digit(digit):
    segments = DIGITS[digit]
    for name, pin in LEDS.items():
        if name in segments:
            pin.on()
        else:
            pin.off()
    
def dp_blink():
    clear()
    for x in range(3):
        LEDS["DP"].on()
        utime.sleep(.05)
        LEDS["DP"].off()
        utime.sleep(.05)

def snake():
    for name in order:
        pin = LEDS[name]
        pin.on()
        utime.sleep(.1)
        pin.off()
        utime.sleep(.1)

def boobs():
    for digit in (8, 0, 0, 8, 5):
        display_digit(digit)
        utime.sleep(.5)
        clear()
        utime.sleep(.5)

def display_digits():
    for digit in range(10):
         print(f"displaying {digit}")
         display_digit(digit)
         utime.sleep(1)

clicks = 0
last_click = 0

def button_pressed(pin):
    global clicks, last_click
    new_time = utime.ticks_ms()
    # debounce
    if (new_time - last_click) > 100: 
        clicks += 1
        last_click = new_time

buttonpin = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_UP)

def game():
    global clicks
    clicks = 0
    digits = range(1,9)
    while True:
        clear()
        dp_blink()
        clicks_before = clicks
        digit = random.choice(digits)
        buttonpin.irq(
            trigger=machine.Pin.IRQ_FALLING,
            handler = button_pressed
            )
        for x in range(10):
            display_digit(digit)
            utime.sleep_ms(400)
            clear()
            utime.sleep_ms(100)
        buttonpin.irq(
            trigger=machine.Pin.IRQ_FALLING,
            handler = None
            )
        #print(f"clicks {clicks}, digit {digit}, clicks_before {clicks_before}")
        dp_blink()
        supplied = clicks - clicks_before
        if supplied == digit:
            print(f"Correct ({digit})")
            snake()
        else:
            print(f"Incorrect (wanted {digit}, got {supplied})")


try:
    clear()
    snake()
    dp_blink()
    game()    
finally:
    for name, pin in LEDS.items():
        pin.off()

    
