import argparse
import enum
import fasteners
import logging
import os
import pexpect
import sys
import time
import signal

from breakonthru.util import teelogger

class Pager:
    """ Uses pjsua to make a call to a SIP number when a USR1/USR2 signal is
        received """
    lastpage = 0

    def __init__(
            self,
            pjsua_bin,
            pjsua_config_file,
            pagingsip,
            pagingduration,
            page_throttle_duration,
            logfile = None,
    ):
        self.child = None
        self.pjsua_bin = pjsua_bin
        self.pjsua_config_file = pjsua_config_file
        self.pagingsip = pagingsip
        self.pagingduration = pagingduration
        self.pagerequested = False
        self.page_throttle_duration = page_throttle_duration
        self.logger = teelogger(logfile)

    def log(self, msg):
        self.logger.info(msg)

    def runforever(self, drainevery=0):
        lock = fasteners.InterProcessLock('/tmp/pager.lock')
        with lock: # protect from 2 instances running same time,
            lock.lockfile.seek(0)
            lock.lockfile.truncate()
            lock.lockfile.write(str(os.getpid()))
            lock.lockfile.flush()
            try:
                self._run(drainevery)
            except KeyboardInterrupt:
                pass

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
                self.log("Page requested")
                now = time.time()
                self.pagerequested = False
                if now > (self.lastpage + self.page_throttle_duration):
                    self.log("Paging")
                    self.lastpage = now
                    self.page()
                else:
                    self.log("Skipping page due to throttle duration")
            if False: #drainevery: # see all output more quickly, for debugging
                now = time.time()
                if now > (last + drainevery):
                    last = now
                    self.child.sendline('echo 1')
                    self.child.expect('>>>') # fail if it died
            time.sleep(.1)

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

    def usr1(self, signum, frame):
        self.log("USR1 received")
        self.pagerequested = True

    def usr2(self, signum, frame):
        self.log("USR2 received")
        self.lastpage = 0
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
    parser.add_argument(
        '--page-throttle-duration',
        help="only page if this many seconds has elapsed since the last page",
        type=int,
        default=30,
    )
    parser.add_argument(
        '--logfile',
        default=None
    )
    args = parser.parse_args()
    maker = Pager(
        args.pjsua_bin,
        args.pjsua_config_file,
        args.paging_sip,
        args.paging_duration,
        args.page_throttle_duration,
        args.logfile,
    )
    signal.signal(signal.SIGUSR1, maker.usr1) # page (throttled) on SIGUSR1
    signal.signal(signal.SIGUSR2, maker.usr2) # page unconditionally on SIGUSR2
    maker.runforever(args.drainevery)
