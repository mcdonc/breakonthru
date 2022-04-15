breakonthru
===========

Door unlock/comms hack for 80s-tastic apartment intercom system.  See
https://www.youtube.com/watch?v=cVQtVz5TQ54 for more info.

On Pi
=====

Create a directory inside the pi user's home directory named "lockit".

Create a Python virtualenv and install breakonthru into it:

   While still in "lockit", create a Python virtual environment "python3 -m venv env"

   Check this software (breakonthru) out into lockit.

   cd into "breakonthru"

   ../env/bin/pip install --upgrade pip setuptools
   export CFLAGS=-fcommon   # to allow RPi.GPIO to build properly
   ../env/bin/pip install -e .

Install supervisor and configure it:

   sudo apt install supervisor

   copy the "client.conf" from the configs/supervisor directory into
   /etc/supervisor/conf.d and change as necessary.

   sudo service supervisor restart

Install asterisk and configure it:

   sudo apt install asterisk

   copy the .conf files from the configs/asterisk directory into /etc/asterisk (it
   will overwrite some, make backups first if you care), and change as necessary.

Install pjsua and configure it:

  Check out https://github.com/pjsip/pjproject into lockit and configure it (no Debian
  package AFAICT).

   sudo apt install build-essential asterisk libbcg729-0 libbcg729-dev ffmpeg \
          libasound2-dev
   git clone git@github.com:pjsip/pjproject.git
   add the file pjproject/pjlib/include/pj/config_site.h; it should have this content:

     #define PJMEDIA_AUDIO_DEV_HAS_ALSA      1
     #define PJMEDIA_AUDIO_DEV_HAS_PORTAUDIO 0
     #define PJMEDIA_HAS_VIDEO  0   

   ./configure; make dep; make

  copy the pjsua.conf file from the configs directory into /home/pi/lockit and
  change as necessary.

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

and then create /etc/asound.conf with following to make the USB sound card the default
device:

   defaults.pcm.card <cardno>
   defaults.ctl.card <cardno>

For me this is

   defaults.pcm.card 1
   defaults.ctl.card 1

Reboot to take effect.

Use alsamixer to set mic and speaker levels (about 3/4 way up works for me for both speaker and mic).

After you set the levels with alsa mixer use "sudo alsactl store" to store the settings persistently
so they'll work across reboots.

If your pi is behind a NAT, you'll need to set up port forwarding from your router to
your pi.  Pass through these ports to the Pi.

  Port 5065 (SIP) both UDP and TCP
  Ports 10000-20000 (SIP media) both UDP and TCP
  
Add a ddns service to your router configuration which gives it a stable hostname.  I
use duckdns.org for this.

Connect SIP softphones like Zoiper to your asterisk server (7001, 7002, etc).

On Internet Host
================

Create a directory inside your home directory named "lockit".

Check this software (breakonthru) out into it.

While still in "lockit", create a Python virtual environment "python3 -m venv env"

cd into "breakonthru"

../env/bin/pip install --upgrade pip setuptools
../env/bin/pip install -e .

sudo apt install supervisor

copy the "server.conf" from the configs/supervisor directory into
/etc/supervisor/conf.d and change as necessary.

copy the production.ini_template into $HOME/lockit/production.ini and change as
necessary.

copy the passwords_template into $HOME/lockit/passwords and change as necessary (see
file for info).

sudo service supervisor restart

Note that you will have to set up Apache/NGINX with SSL proxying to both the
doorserver port and the webapp port for everything to work properly.  See
configs/apache for sample configurations.
