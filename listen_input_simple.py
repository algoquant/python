#!/usr/bin/env python3
"""
Simple Python script that listens for input and handles Ctrl-C gracefully
"""

import signal
import sys

def signal_handler(sig, frame):
    """Handle Ctrl-C (SIGINT) gracefully"""
    print("\n\nCtrl-C pressed! Exiting gracefully...")
    sys.exit(0)

def main():
    """Main function"""
    # Set up signal handler for Ctrl-C
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Simple Input Listener")
    print("Type anything and press Enter")
    print("Press Ctrl-C to quit")
    print("-" * 30)
    
    try:
        while True:
            try:
                # Get input from user
                user_input = input(">>> ")
                
                # Process the input
                if user_input.strip():
                    print(f"You typed: {user_input}")
                else:
                    print("(empty input)")
                    
            except EOFError:
                # Handle EOF (Ctrl-D)
                print("\nEOF received. Goodbye!")
                break
                
    except KeyboardInterrupt:
        # Backup handler (shouldn't reach here due to signal handler)
        print("\nKeyboard interrupt. Goodbye!")

if __name__ == "__main__":
    main()
