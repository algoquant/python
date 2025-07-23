#!/usr/bin/env python3
"""
Python script that listens to input and quits when it receives Ctrl-C
"""

import signal
import sys
import time

def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl-C) gracefully"""
    print("\n\nReceived Ctrl-C (SIGINT)")
    print("Cleaning up and exiting...")
    sys.exit(0)

def main():
    """Main function that listens for input"""
    # Register the signal handler for SIGINT (Ctrl-C)
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Input Listener Started")
    print("Type anything and press Enter to see it echoed back")
    print("Press Ctrl-C to quit gracefully\n")
    
    try:
        while True:
            try:
                # Listen for user input
                user_input = input("Enter something (or Ctrl-C to quit): ")
                
                # Echo the input back
                print(f"You entered: {user_input}")
                
                # Optional: Check for specific quit commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Quit command received. Exiting...")
                    break
                    
            except EOFError:
                # Handle EOF (Ctrl-D on Unix/Linux, Ctrl-Z on Windows)
                print("\nEOF received. Exiting...")
                break
                
    except KeyboardInterrupt:
        # This shouldn't be reached due to signal handler, but just in case
        print("\nKeyboard interrupt received. Exiting...")
    
    print("Goodbye!")

if __name__ == "__main__":
    main()
