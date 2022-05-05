breakonthru
+++++++++++

Door unlock/comms hack for 80s-tastic apartment intercom system.  See
https://www.youtube.com/playlist?list=PLa01scHy0YEldOY9phr0YoTnNXKxjtrjs
for more info.

On Pi
=====

- Create a directory inside the pi user's home directory named "lockit"::

    mkdir /home/pi/lockit

Install pjsua and configure it
------------------------------

  - Check out https://github.com/pjsip/pjproject into /home/pi/lockit and
    configure it (no Debian package AFAICT)::

      sudo apt install build-essential asterisk libbcg729-0 libbcg729-dev ffmpeg \
              libasound2-dev
      git clone git@github.com:pjsip/pjproject.git
      
  - Add the file ``pjproject/pjlib/include/pj/config_site.h``; it should have
    this content::

      #define PJMEDIA_AUDIO_DEV_HAS_ALSA      1
      #define PJMEDIA_AUDIO_DEV_HAS_PORTAUDIO 0
      #define PJMEDIA_HAS_VIDEO  0

  - Build pjproject::

      ./configure; make dep; make

  - Copy the ``pjsua.conf_template`` file from the ``breakonthru/configs/pi``
    directory into ``/home/pi/lockit/pjsua.conf`` and change as necessary.

Configure audio
---------------

- Find your USB sound card with::

    cat /proc/asound/cards

  For me this outputs::

    0 [Headphones     ]: bcm2835_headpho - bcm2835 Headphones
                         bcm2835 Headphones
    1 [Device         ]: USB-Audio - USB Audio Device
                         C-Media Electronics Inc. USB Audio Device at
                         usb-0000:01:00.0-1.4, full speed
    2 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0
                         vc4-hdmi-0
    3 [vc4hdmi1       ]: vc4-hdmi - vc4-hdmi-1
                            vc4-hdmi-1

  And then create /etc/asound.conf with following to make the USB sound card the
  default device::

    defaults.pcm.card <cardno>
    defaults.ctl.card <cardno>

  For me this is::

    defaults.pcm.card 1
    defaults.ctl.card 1

- Reboot to take effect.

- Use ``alsamixer`` to set mic and speaker levels (about 2/3 way up works for me for
  both speaker and mic).

- After you set the levels with ``alsamixer`` use ``sudo alsactl store`` to store
  the settings persistently so they'll work across reboots.

Create a Python virtualenv and install breakonthru into it
----------------------------------------------------------

- While in ``/home/pi/lockit``, create a Python virtual environment::

    python3 -m venv env

- Check this software (breakonthru) out into ``/home/pi/lockit`` and install it into
  the virtualenv::

    cd /home/pi/lockit
    git clone git@github.com:mcdonc/breakonthru.git
    cd breakonthru
    ../env/bin/pip install --upgrade pip setuptools
    export CFLAGS=-fcommon   # to allow RPi.GPIO to build properly
    ../env/bin/pip install -e .

Install supervisor and configure it
-----------------------------------

-  ``sudo apt install supervisor``

- copy the ``breakonthru/configs/pi/supervisor/lockit.conf`` file into
  ``/etc/supervisor/conf.d/lockit.conf`` and change as necessary.

  copy the ``breakonthru/configs/pi/client.ini_template`` file into
  ``/home/pi/lockit/client.ini`` and change as necessary.

- ``sudo service supervisor restart``

Install asterisk and configure it
---------------------------------

- ``sudo apt install asterisk``

- copy the ``.conf`` files from the ``breakonthru/configs/pi/asterisk``
  directory into ``/etc/asterisk`` (it will overwrite some, make backups first
  if you care), and change as necessary.

Network configuraton
--------------------

- If your pi is behind a NAT, you'll need to set up port forwarding from your router
  to your pi.  Pass through these ports to the pi::

    Port 5065 UDP (SIP)
    Ports 10000-20000 UDP (SIP media)
  
- Add a ddns service to your router configuration which gives it a stable
  hostname.  I use duckdns.org for this.  Let's pretend this hostname is
  ``lockit.duckdns.org`` for docs purposes.

- Connect SIP softphones like MizuDroid or Zoiper to your asterisk server
  (7002, 7003, etc).  The domain you provide to each softphone instance will
  look something like ``7002@lockit.duckdns.org:5065``, although each has their
  own way of asking you (sometimes separately) for the username and the
  hostname/port.  The password for this account will be the secret in the
  ``/etc/asterisk/sip.conf`` associated with 7002.  MizuDroid is totally free and
  very good, but is only available on Android, AFAICT.  Zoiper's nagware and
  feature-limited edition is also free and is available for Android, Windows,
  Linux, and iOS.  Its "premium" edition that adds the missing features and
  stops nagging is like ten bucks or something.

On Internet Host
================

- Create a directory inside your home directory named ``lockit``.

- Check this software (breakonthru) out into it::

    cd $HOME/lockit
    git clone git@github.com:mcdonc/breakonthru.git

- While still in ``$HOME/lockit``, create a Python virtual environment and install
  ``breakonthru`` into it::

    python3 -m venv env
    cd breakonthru
    ../env/bin/pip install --upgrade pip setuptools
    ../env/bin/pip install -e .

- Install supervisor::

    sudo apt install supervisor

- copy the ``breakonthru/configs/internethost/supervisor/lockit.conf`` file
  into ``/etc/supervisor/conf.d`` and change as necessary.

- copy the ``breakonthru/configs/internethost/production.ini_template`` into
  ``$HOME/lockit/production.ini`` and change as necessary.

- copy the ``breakonthru/configs/internethost/passwords_template`` into
  ``$HOME/lockit/passwords`` and change as necessary (see file for info).

- copy the ``breakonthru/configs/internethost/server.ini_template`` into
  ``$HOME/lockit/server.ini`` and change as necessary.

- ``sudo service supervisor restart``

- Note that you will have to set up Apache/NGINX with SSL proxying to both the
  doorserver port (e.g. "wss://lockitws.mydomain.org/") and the webapp port
  (e.g. "https://lockit.mydomain.org/") for everything to work properly.  See
  breakonthru/configs/internethost/apache for sample configurations.  It is
  easiest (and cheapest, ironically) to use LetsEncrypt for this.

Q&A
===

You can call the front door by dialing its extension (7001 if you kept default
config).  ``pjsua`` will autoanswer due to ``--auto-answer 200`` in
``pjsua.conf``.

What happens when you call the front door and it's already on a call?  It seems like 
a poor man's conference call. Both can hear the front door mic.  Both can speak to
the front door speaker.  But clients can't hear each other directly, although they 
can hear each other through the front door speaker feeding back into the front door mic.
I had thought maybe pjsua's ``--auto-conf`` option would change this behavior, but
it doesn't seem to (with limited testing).

Why stun and ice in ``pjsua.conf``? Seems to make off-LAN *inbound* calling
work better, but it's lightly tested and may be unneccessary.

Does the person who presses the call button hear a phone dialing?  Yes.

What happens if somebody spams the callbutton?  Pages are throttled to one
every 15 seconds (configurable in client.ini via ``page_throttle_duration``).

There is no "not answering" message played or voicemail box set up in Asterisk to
handle never-answered calls from the front door.  It's possible to do, I just didn't.

Calls between the front door and humans are limited via ``pjsua.conf`` to a
total duration of 120 seconds if you just copy it out of breakonthru/config
(it's ``--duration 120``).

Calls will ring for at most 30 seconds if no one answers when the button is pressed.
You can change this in asterisk's extensions.conf (in each ``Dial`` directive).

Two doors are supported, represented by ``unlock0_gpio_pin`` and ``unlock1_gpio_pin``
in the ``client.ini`` configuration file on the pi.  You may need to change the
``index.pt`` HTML in breakonthru/templates if you have fewer doors (just delete
one of the buttons).  You may need to change both the ``index.pt`` (add more
buttons) and the ``breakonthru/scripts/doorclient.py`` file (to accept more
``unlockX_gpio_pin`` configuration values) if you have more doors.

Doors will stay unlocked for 5 seconds when an unlock request is successful.
This is configurable via the ``door_unlocked_duration`` value in the
``client.ini`` config file.

You might play around with ``pjsua.conf`` ``--ec-tail`` and related options to try to
get some echo cancellation wrt front door speaker feeding back into front door
mic.  My limited attempts at this were not successful.

Why do I use`` gpiozero`` instead of raw ``RPi.GPIO``?  I used the latter initially,
but I had problems where sending volage to the output pin (for the door unlock)
would trigger the input pin (for the callbutton detector).  It would also
sometimes trigger with AC power fluctuations (hilariously the call button would
trigger when I turned my soldering iron or box fan on or off). I tore my hair
out for days trying to understand why I was getting crosstalk between input and
output pins, and hair-trigger response to power fluctuations.  It would be
interesting to know why, but I've not had time to figure it out.  Although I
didn't get to the bottom of this, switching to ``gpiozero`` made the problem go
away.

Why is ``RPi.GPIO`` required by the breakonthru package's setup.py, if, as you
say, ``RPi.GPIO`` was doing poorly for you?  I'm sure the problem was how I was
*using* the ``RPi.GPIO`` package, not how it works.  If ``RPi.GPIO`` is
installed, ``gpiozero`` will use it to do pin detection.  If ``RPi.GPIO`` is
*not* installed, ``gpiozero`` uses experimental native pin detection.
Experimental native pin detection misses most button presses in my testing
(only maybe 1 in 5 are detected), so it is not really viable.  But somehow
``gpiozero`` uses ``RPi.GPIO`` properly, whereas I did not while I used it raw.
¯\_(ツ)_/¯

But even with ``RPi.GPIO`` installed, callbutton press detection via
``gpiozero`` is not perfect in my setup.  Some totally legitimate button
presses are missed.  This is not due to bad debouncing, or due to the button or
the relay.  The button and the relay are doing their jobs fine, I verified this
independently.  Anyway, the upshot is that only maybe 80% of button presses are
detected correctly.  It's irritating but I have no clue why yet.

Why is the ``callbutton_bouncetime`` "2"?  2 means 2 milliseconds.  In my
configuration, the callbutton itself is hooked up to a relay, so it's the relay's
mechanical switch that is being measured by the bounce time, not the actual
call button's mechanical switch.  The relay has a very low bouncetime of about
400 microseconds (I measured it with a scope), so 2 milliseconds is plenty.  You
may need to change this if you use some other method of relaying the call button
into the Pi or if your relay is somehow terrible.  FWIW, the bouncetime of the
actual callbutton switch I'm using for testing is close to 2 milliseconds.

Why use ``supervisor`` instead of a systemd unit to keep the various services
running when they crash?  I'm too lazy to look up the docs for the systemd unit
config file, and I am the author of ``supervisor``.  Patches accepted.  Do
note the logging output requirements, though.
