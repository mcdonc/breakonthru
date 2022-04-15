import argparse
import enum
import fasteners
import logging
import pexpect
import sys
import time
import signal


class Pager:
    """ Uses pjsua to make a call to a SIP number when the USR1 signal is received """

    def __init__(self, pjsua_bin, pjsua_config_file, pagingsip, pagingduration):
        self.child = None
        self.pjsua_bin = pjsua_bin
        self.pjsua_config_file = pjsua_config_file
        self.pagingsip = pagingsip
        self.pagingduration = pagingduration
        self.pagerequested = False

    def runforever(self, drainevery=0):
        lockfile = fasteners.InterProcessLock('/tmp/pager.lock')
        with lockfile: # protect from 2 instances running same time
            self._run(drainevery)

    def _run(self, drainevery=0):
        self.child = pexpect.spawn(
            f'{self.pjsua_bin} --config-file {self.pjsua_config_file}',
            encoding='utf-8',
            timeout=2,
        )
        self.child.logfile_read = sys.stdout
        self.child.expect('registration success') # fail if not successful

        last = time.time()

        while True:
            if self.pagerequested:
                self.pagerequested = False
                self.page()
            if drainevery: # see all output more quickly, for debugging
                now = time.time()
                if now > (last + drainevery): # drain stderr/stdout (required?)
                    last = now
                    self.child.sendline('echo 1')
                    self.child.expect('>>>') # fail if it died
            time.sleep(.5)

    def page(self):
        self.make_call(self.pagingsip, self.pagingduration)

    def make_call(self, sip, duration=sys.maxsize):
        child = self.child
        self.hangup()
        child.sendline('m')
        child.expect('Make call:')
        child.sendline(sip)
        i = child.expect(['CONFIRMED', 'DISCONN', pexpect.EOF, pexpect.TIMEOUT])
        start = time.time()
        if i == 0: # CONFIRMED, call ringing
            while True: # wait til the duration is over to hang up
                i = child.expect(['DISCONN', pexpect.EOF, pexpect.TIMEOUT])
                if i != 2: # if it's disconnected or program crashed
                    break
                if time.time() >= (start + duration):
                    break
            self.hangup()

    def hangup(self):
        self.child.sendline('h')
        self.child.expect('>>>')

    def close(self, force=True):
        time.sleep(1) # allow any pending operations to complete
        self.child.close(force=force)

    def sighandler(self, signum, frame):
        self.pagerequested = True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--pjsua-bin', help="Path to the 'pjsua' binary executable",
        required=True
    )
    parser.add_argument(
        '--pjsua-config-file', help="path to pjsua configuration file",
        required=True
    )
    parser.add_argument(
        '--paging-sip', help="The SIP address to call when the callbutton is pressed",
        required=True
    )
    parser.add_argument(
        '--paging-duration',
        help="The max number of seconds allowed for voice communications after a page",
        type=int,
        default=100
    )
    parser.add_argument(
        '--drainevery',
        help="(debugging) ask pexpect for output every 'drainevery' seconds",
        type=int,
        default=0,
    )
    args = parser.parse_args()
    maker = Pager(
        args.pjsua_bin,
        args.pjsua_config_file,
        args.paging_sip,
        args.paging_duration
    )
    signal.signal(signal.SIGUSR1, maker.sighandler) # page on SIGUSR1
    maker.runforever(args.drainevery)
