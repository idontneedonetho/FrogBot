# commands/watchdog.py

import os
import sys
import time
import subprocess
import signal

WATCHDOG_PID_FILE = 'watchdog.pid'
RESTART_FLAG_FILE = 'restart.flag'

def signal_handler(signum, frame):
    remove_pid_file()
    sys.exit("Watchdog exiting due to kill signal.")

signal.signal(signal.SIGTERM, signal_handler)

def write_pid_file():
    with open(WATCHDOG_PID_FILE, 'w') as pid_file:
        pid_file.write(str(os.getpid()))

def check_single_instance():
    if os.path.exists(WATCHDOG_PID_FILE):
        with open(WATCHDOG_PID_FILE, 'r') as pid_file:
            existing_pid = int(pid_file.read())
            try:
                os.kill(existing_pid, 0)
                return False
            except OSError:
                pass
    write_pid_file()
    return True

if not check_single_instance():
    sys.exit("Another instance of the watchdog is already running.")

while True:
    if os.path.exists(RESTART_FLAG_FILE):
        time.sleep(3)
        os.remove(RESTART_FLAG_FILE)
        subprocess.run([sys.executable, 'bot.py'])
    time.sleep(10)

def remove_pid_file():
    if os.path.exists(WATCHDOG_PID_FILE):
        os.remove(WATCHDOG_PID_FILE)

atexit.register(remove_pid_file)