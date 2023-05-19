import machine
import random
import utime

# The segments of the display have letter ids.

#  ---A----
# |        |
# F        B
# |        |
# |---G----|
# |        |
# E        C
# |        |
#  ---D----  . DP


SEGMENTS = {
    # mapping of segment id to GPIO PIN on the Pico that turns it on and off
    "A": machine.Pin(9, machine.Pin.OUT),  # (to pin 7 on unit)
    "B": machine.Pin(3, machine.Pin.OUT),  # (to pin 6 on unit)
    "C": machine.Pin(5, machine.Pin.OUT),  # (to pin 4 on unit)
    "D": machine.Pin(6, machine.Pin.OUT),  # (to pin 2 on unit)
    "E": machine.Pin(7, machine.Pin.OUT),  # (to pin 1 on unit)
    "F": machine.Pin(2, machine.Pin.OUT),  # (to pin 9 on unit)
    "G": machine.Pin(8, machine.Pin.OUT),  # (to pin 10 on unit)
    "DP": machine.Pin(4, machine.Pin.OUT),  # (to pin 5 on unit)
}

# A mapping of a digit to the segment ids that should be turned on to display
# that particular digit
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

BUZZER_PIN =  machine.Pin(0)

def clear():
    """Turn off all segments"""
    for name, pin in SEGMENTS.items():
        pin.off()


def display_digit(digit):
    """Display a digit"""
    segments = DIGITS[digit]
    for name, pin in SEGMENTS.items():
        if name in segments:
            pin.on()
        else:
            pin.off()


def dp_blink():
    """Turn off all segments then blink the decimal point segment a few
    times"""
    clear()
    for x in range(3):
        SEGMENTS["DP"].on()
        utime.sleep(0.05)
        SEGMENTS["DP"].off()
        utime.sleep(0.05)


def snake():
    """Animate a snake on the display"""
    order = ["G", "F", "A", "B", "G", "E", "D", "C"]
    for name in order:
        pin = SEGMENTS[name]
        pin.on()
        utime.sleep(0.1)
        pin.off()
        utime.sleep(0.1)


def display_digits():
    """Display each digit 0-9 in order"""
    for digit in range(10):
        display_digit(digit)
        utime.sleep(0.1)


clicks = 0
last_click = 0


def button_pressed(pin):
    """Interrupt handler that is called when our button is clicked"""
    global clicks, last_click
    new_time = utime.ticks_ms()
    # debounce
    if (new_time - last_click) > 225:
        clicks += 1
        last_click = new_time
        make_noise(512, 0.1)


buttonpin = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_UP)


def start_listening_for_clicks():
    buttonpin.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_pressed)


def stop_listening_for_clicks():
    buttonpin.irq(trigger=machine.Pin.IRQ_FALLING, handler=None)  # type: ignore

def make_noise(freq, duration=1.0):
    buzzer = machine.PWM(BUZZER_PIN)
    # Set a pwm frequency
    buzzer.freq(freq)
    # Set the buzzer duty value
    # this serves as volume control
    # Max volume is a duty value of 512
    buzzer.duty_u16(50)
    # Let the sound ring for a certain duration
    utime.sleep(duration)
    #  Turn off the pulse by setting the duty to 0
    buzzer.duty_u16(0)
    buzzer.deinit()

def game():
    """
    The 7-segment display will show a digit.  If you click exactly that many
    times on the button connected to BUTTONPIN within about 5 seconds, it will
    show the snake animation and make a win noise.  If you click too many times
    or too few times it will make a lose noise.
    """
    global clicks
    digits = range(1, 9)
    while True:
        clear()
        dp_blink()
        clicks_before = clicks
        digit = random.choice(digits)
        make_noise(1047)
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
            make_noise(2000, .1)
            snake()
        else:
            print(f"Incorrect (wanted {digit}, got {supplied})")
            make_noise(500, .1)


try:
    clear()
    display_digits()
    snake()
    dp_blink()
    game()
finally:
    clear()
    make_noise(200, .1)
