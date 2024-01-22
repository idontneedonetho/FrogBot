# commands/watchdog.py

import os
import sys
import time
import subprocess
import signal
import atexit
import logging
import psutil

WATCHDOG_PID_FILE = 'watchdog.pid'
RESTART_FLAG_FILE = 'restart.flag'
LOG_FILE = 'watchdog.log'

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def remove_pid_file():
    try:
        if os.path.exists(WATCHDOG_PID_FILE):
            os.remove(WATCHDOG_PID_FILE)
            logging.info("PID file removed.")
    except Exception as e:
        logging.error(f"Error removing PID file: {e}")
atexit.register(remove_pid_file)

def signal_handler(signum, frame):
    logging.info(f"Watchdog exiting due to signal: {signum}")
    remove_pid_file()
    sys.exit(f"Watchdog exiting due to kill signal: {signal.Signals(signum).name}.")
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def write_pid_file():
    try:
        with open(WATCHDOG_PID_FILE, 'w') as pid_file:
            pid_file.write(str(os.getpid()))
            logging.info("PID file written.")
    except Exception as e:
        logging.error(f"Error writing PID file: {e}")
        sys.exit("Failed to write PID file.")

def check_single_instance():
    if os.path.exists(WATCHDOG_PID_FILE):
        with open(WATCHDOG_PID_FILE, 'r') as pid_file:
            existing_pid = int(pid_file.read())
            if psutil.pid_exists(existing_pid):
                try:
                    p = psutil.Process(existing_pid)
                    if p.is_running():
                        logging.warning(f"Another instance of the watchdog (PID: {existing_pid}) is already running.")
                        return False
                except psutil.NoSuchProcess:
                    logging.info(f"No other watchdog instance is running. Previous PID: {existing_pid}")
            else:
                logging.info(f"PID file exists but the process does not exist. Previous PID: {existing_pid}")
    write_pid_file()
    return True

if not check_single_instance():
    sys.exit("Another instance of the watchdog is already running.")

while True:
    try:
        if os.path.exists(RESTART_FLAG_FILE):
            logging.info("Restart flag file detected. Restarting bot.")
            time.sleep(3)
            os.remove(RESTART_FLAG_FILE)
            subprocess.run([sys.executable, 'bot.py'])
    except Exception as e:
        logging.error(f"Error during the watchdog loop: {e}")
    time.sleep(10)
