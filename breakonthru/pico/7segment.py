import machine
import random
import utime

# The segments of the display have ids.
#
#  ---A----
# |        |
# F        B
# |        |
# |---G----|
# |        |
# E        C
# |        |
#  ---D----  . DP
#

SEGMENTS = {
    # mapping of segment id to GPIO PIN
    "A": machine.Pin(9,machine.Pin.OUT),
    "B": machine.Pin(3,machine.Pin.OUT),
    "C": machine.Pin(5,machine.Pin.OUT),
    "D": machine.Pin(6,machine.Pin.OUT),
    "E": machine.Pin(7,machine.Pin.OUT),
    "F": machine.Pin(2,machine.Pin.OUT),
    "G": machine.Pin(8,machine.Pin.OUT),
    "DP": machine.Pin(4,machine.Pin.OUT),
    }

# A mapping of a digit to the segment ids
# that should be turned on to display that
# particular digit
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
    """ Turn off all segments """
    for name, pin in SEGMENTS.items():
        pin.off()

def display_digit(digit):
    """ Display a digit """
    segments = DIGITS[digit]
    for name, pin in SEGMENTS.items():
        if name in segments:
            pin.on()
        else:
            pin.off()
    
def dp_blink():
    """ Turn off all segments then blink the decimal 
    point segment a few times"""
    clear()
    for x in range(3):
        SEGMENTS["DP"].on()
        utime.sleep(.05)
        SEGMENTS["DP"].off()
        utime.sleep(.05)

def snake():
    """ Animate a snake on the display """
    order = [ "G", "F", "A", "B", "G", "E", "D", "C" ]
    for name in order:
        pin = SEGMENTS[name]
        pin.on()
        utime.sleep(.1)
        pin.off()
        utime.sleep(.1)

def display_digits():
    """ Display each digit 0-9 in order """
    for digit in range(10):
         print(f"displaying {digit}")
         display_digit(digit)
         utime.sleep(.1)

clicks = 0
last_click = 0

def button_pressed(pin):
    """ Interrupt handler that is called when our 
    button is clicked """
    global clicks, last_click
    new_time = utime.ticks_ms()
    # debounce
    if (new_time - last_click) > 100: 
        clicks += 1
        last_click = new_time

buttonpin = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_UP)

def start_listening_for_clicks():
    buttonpin.irq(
        trigger=machine.Pin.IRQ_FALLING,
        handler = button_pressed
    )


def stop_listening_for_clicks():
    buttonpin.irq(
        trigger=machine.Pin.IRQ_FALLING,
        handler = None # type: ignore
    )

def game():
    global clicks
    digits = range(1,9)
    while True:
        clear()
        dp_blink()
        clicks_before = clicks
        digit = random.choice(digits)
        start_listening_for_clicks()
        for x in range(10):
            display_digit(digit)
            utime.sleep_ms(400)
            clear()
            utime.sleep_ms(100)
        stop_listening_for_clicks()
        dp_blink()
        supplied = clicks - clicks_before
        if supplied == digit:
            print(f"Correct ({digit})")
            snake()
        else:
            print(f"Incorrect (wanted {digit}, got {supplied})")


try:
    clear()
    display_digits()
    snake()
    dp_blink()
    game()    
finally:
    clear()
