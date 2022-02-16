breakonthru
===========

Door unlock/comms hack for 80s-tastic apartment intercom system.

On Pi
=====

Create a directory inside the pi user's home directory named "lockit".

Check this software (breakonthru) out into it.

Also check out https://github.com/gavv/webrtc-cli into it.

Build webrtc-cli as per its "make" based instructions.

While still in "lockit", create a Python virtual environment "python3 -m venv env"

cd into "breakonthru"

../env/bin/pip install --upgrade pip setuptools
export CFLAGS=-fcommon   # to allow RPi.GPIO to build properly
../env/bin/pip install -e .

sudo apt install supervisor

copy the "client.conf" from the configs/supervisor directory into
/etc/supervisor/conf.d and change as necessary.

sudo service supervisor restart

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
