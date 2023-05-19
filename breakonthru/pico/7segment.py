import machine
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

try:
    clear()
    for x in range(1):
        for name in order:
            print(f"{name} on")
            pin = LEDS[name]
            pin.on()
            utime.sleep(.1)
            pin.off()
            utime.sleep(.1)

    dp_blink()

    for digit in range(10):
        print(f"displaying {digit}")
        display_digit(digit)
        utime.sleep(1)

    dp_blink()

    for digit in (8, 0, 0, 8, 5):
        display_digit(digit)
        utime.sleep(.5)
        clear()
        utime.sleep(.5)
    
finally:
    for name, pin in LEDS.items():
        pin.off()

