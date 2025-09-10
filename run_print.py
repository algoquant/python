#!/usr/bin/env python3

"""
Prints a text message every 5 seconds.
Accepts a command line argument for the text to print.

Run the script in the terminal, to print the text "test_to_print":
    python3 -u /Users/jerzy/Develop/Python/run_print.py test_to_print

Run the script with nohup to keep it running after the terminal is closed.
Add the -u flag to prevent buffering of the output.
  nohup python3 -u /Users/jerzy/Develop/Python/run_print.py test_to_print > /Users/jerzy/Develop/data/trading/test.log 2>&1 &
The script '2>&1' is a combination of two shell redirection operators:
	'2' refers to stderr (standard error).
	'>&1' redirects stderr to wherever stdout (standard output) is going.
	So '2>&1' means redirect stderr to the same place as stdout.
Get the PID for the script 'run_print.py'
    ps aux | grep run_print.py
Kill the process 'run_print.py' by using its PID
    kill 32286
Run the echo command in the terminal, to get the PID and save it to the file 'run_print.pid':
    echo $! > run_print.pid

"""

import time
import signal
import sys

def signal_handler(sig, frame):
    print("\nCtrl-C pressed! Exiting...")
    sys.exit(0)

def main():
    # Set up signal handler for Ctrl-C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Get the text from the command line
    if len(sys.argv) > 1:
        text_to_print = sys.argv[1]
    else:
        # Get text from user input
        text_to_print = input("Enter text_to_print: ")

    # Debug: Write the received args to a temp file
    # with open("/Users/jerzy/Develop/data/trading/run_print_args.log", "a") as dbg:
    #     dbg.write(f"{sys.argv!r}\n")

    try:
        while True:
            print(text_to_print)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nScript stopped by user.")

if __name__ == "__main__":
    main()
