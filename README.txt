breakonthru
===========

Door unlock/comms hack for 80s-tastic apartment intercom system.  See
https://www.youtube.com/watch?v=cVQtVz5TQ54 for more info.

On Pi
=====

Create a directory inside the pi user's home directory named "lockit".

Check this software (breakonthru) out into it.

Also check out https://github.com/pjsip/pjproject into it and build it:

   sudo apt install build-essential asterisk libbcg729-0 libbcg729-dev ffmpeg libasound2-dev
   git clone git@github.com:pjsip/pjproject.git
   add the file pjproject/pjlib/include/pj/config_site.h; it should have this content:

     #define PJMEDIA_AUDIO_DEV_HAS_ALSA      1
     #define PJMEDIA_AUDIO_DEV_HAS_PORTAUDIO 0
     #define PJMEDIA_HAS_VIDEO  0   

   ./configure; make dep; make

While still in "lockit", create a Python virtual environment "python3 -m venv env"

cd into "breakonthru"

../env/bin/pip install --upgrade pip setuptools
export CFLAGS=-fcommon   # to allow RPi.GPIO to build properly
../env/bin/pip install -e .

sudo apt install supervisor

copy the "client.conf" from the configs/supervisor directory into
/etc/supervisor/conf.d and change as necessary.

copy the .conf files from the configs/asterisk directory into /etc/asterisk (it
will overwrite some, make backups first if you care), and change as necessary.

copy the pjsua.conf file from the configs directory into /home/pi/lockit and
change as necessary.

To give access to non-LAN devices to your asterisk server, set up port
forwarding from your router to lock802 (*** explain more), and add a ddns
service to your router which gives it a stable hostname.

sudo service supervisor restart

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
