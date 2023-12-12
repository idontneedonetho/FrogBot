# startbot.py

import subprocess
import sys
import time

def main():
    while True:
        print("Starting bot...")
        process = subprocess.Popen([sys.executable, "bot.py"])
        process.wait()  # Wait for the bot process to exit
        time.sleep(5)   # Wait for a few seconds before restarting

if __name__ == "__main__":
    main()
