breakonthru
===========

Door unlock/comms hack for 80s-tastic apartment intercom system.  See
https://youtu.be/FevUnaPQwMM for more info.

On Pi
=====

Create a directory inside the pi user's home directory named "lockit":

    mkdir /home/pi/lockit

Install pjsua and configure it:

    Check out https://github.com/pjsip/pjproject into /home/pi/lockit and configure
    it (no Debian package AFAICT).

     sudo apt install build-essential asterisk libbcg729-0 libbcg729-dev ffmpeg \
            libasound2-dev
     git clone git@github.com:pjsip/pjproject.git
     add the file pjproject/pjlib/include/pj/config_site.h; it should have this content:

       #define PJMEDIA_AUDIO_DEV_HAS_ALSA      1
       #define PJMEDIA_AUDIO_DEV_HAS_PORTAUDIO 0
       #define PJMEDIA_HAS_VIDEO  0   

     ./configure; make dep; make

    copy the pjsua.conf file from the breakonthru/configs directory into
    /home/pi/lockit/pjsua.conf and change as necessary.

Configure audio:

    Find your USB sound card with:

       cat /proc/asound/cards

    For me this outputs:

       0 [Headphones     ]: bcm2835_headpho - bcm2835 Headphones
                            bcm2835 Headphones
       1 [Device         ]: USB-Audio - USB Audio Device
                            C-Media Electronics Inc. USB Audio Device at
                            usb-0000:01:00.0-1.4, full speed
       2 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0
                            vc4-hdmi-0
       3 [vc4hdmi1       ]: vc4-hdmi - vc4-hdmi-1
                            vc4-hdmi-1

    and then create /etc/asound.conf with following to make the USB sound card the
    default device:

       defaults.pcm.card <cardno>
       defaults.ctl.card <cardno>

    For me this is:

       defaults.pcm.card 1
       defaults.ctl.card 1

    Reboot to take effect.

    Use alsamixer to set mic and speaker levels (about 3/4 way up works for me for
    both speaker and mic).

    After you set the levels with alsa mixer use "sudo alsactl store" to store the
    settings persistently so they'll work across reboots.

Create a Python virtualenv and install breakonthru into it:

   While in "/home/pi/lockit", create a Python virtual environment:

      python3 -m venv env

   Check this software (breakonthru) out into /home/pi/lockit.

   cd into "breakonthru"

   ../env/bin/pip install --upgrade pip setuptools
   export CFLAGS=-fcommon   # to allow RPi.GPIO to build properly
   ../env/bin/pip install -e .

Install supervisor and configure it:

   sudo apt install supervisor

   copy the "client.conf" from the breakonthru/configs/supervisor directory into
   /etc/supervisor/conf.d/client.conf and change as necessary.

   copy the "client.ini_template" from the breakonthru/configs directory into
   /home/pi/lockit/client.ini and change as necessary.

   sudo service supervisor restart

Install asterisk and configure it:

   sudo apt install asterisk

   copy the .conf files from the breakonthru/configs/asterisk directory into
   /etc/asterisk (it will overwrite some, make backups first if you care), and
   change as necessary.

Network configuraton:

    If your pi is behind a NAT, you'll need to set up port forwarding from your router
    to your pi.  Pass through these ports to the pi.

      Port 5065 (SIP) both UDP and TCP
      Ports 10000-20000 (SIP media) both UDP and TCP
  
    Add a ddns service to your router configuration which gives it a stable hostname.  I
    use duckdns.org for this.

    Connect SIP softphones like Zoiper to your asterisk server (7002, 7003, etc).

On Internet Host
================

Create a directory inside your home directory named "lockit".

Check this software (breakonthru) out into it.

While still in "lockit", create a Python virtual environment "python3 -m venv env"

cd into "breakonthru"

../env/bin/pip install --upgrade pip setuptools
../env/bin/pip install -e .

sudo apt install supervisor

copy the "server.conf" from the breakonthru/configs/supervisor directory into
/etc/supervisor/conf.d and change as necessary.

copy the production.ini_template into $HOME/lockit/production.ini and change as
necessary.

copy the passwords_template into $HOME/lockit/passwords and change as necessary (see
file for info).

sudo service supervisor restart

Note that you will have to set up Apache/NGINX with SSL proxying to both the
doorserver port and the webapp port for everything to work properly.  See
breakonthru/configs/apache for sample configurations.

Q&A
===

You can call the front door by dialing its extension (7001 if you kept default
config).  pjsua will autoanswer.

What happens when you call the front door and it's already on a call?  It seems like 
a poor man's conference call. Both can hear the front door mic.  Both can speak to
the front door speaker.  But clients can't hear each other directly, although they 
can hear each other through the front door speaker feeding back into the front door mic.
I had thought maybe pjsua's --auto-conf option would change this behavior, but
it doesn't seem to (with limited testing).

What happens if you have Wifi calling on on your phone?  No clue.

Why stun and ice in pjsua.conf? Seems to make off-LAN *inbound* calling work better,
but it's lightly tested and may be unneccessary.

Does the person who presses the front door button hear a phone dialing?  Yes.

What happens if somebody spams the callbutton?  Pages are throttled to one
every 30 seconds (configurable in client.ini via page_throttle_duration).

There is no "not answering" message played or voicemail box set up in Asterisk to
handle never-answered calls from the front door.  It's possible to do, I just didn't.

Calls are limited via pjsua.conf to a total duration of 120 seconds if you just
copy it out of breakonthru/config (it's --duration 120).

Calls will ring for at most 30 seconds if no one answers when the button is pressed.
You can change this in asterisk's extensions.conf (in each Dial directive).

You might play around with pjsua.conf --ec-tail and related options to try to
get some echo cancellation wrt front door speaker feeding back into front door
mic.  My limited attempts at this were not successful.
