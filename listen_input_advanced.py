#!/usr/bin/env python3
"""
Advanced Python script that continuously listens and processes input
with graceful Ctrl-C handling and non-blocking input
"""

import signal
import sys
import time
import threading
from datetime import datetime
import select
import os

class InputListener:
    def __init__(self):
        self.running = True
        self.input_thread = None
        
    def signal_handler(self, sig, frame):
        """Handle SIGINT (Ctrl-C) gracefully"""
        print("\n\nReceived Ctrl-C (SIGINT)")
        print("Shutting down gracefully...")
        self.running = False
        
        # Wait for input thread to finish
        if self.input_thread and self.input_thread.is_alive():
            print("Waiting for input thread to finish...")
            self.input_thread.join(timeout=1.0)
        
        print("Cleanup complete. Goodbye!")
        sys.exit(0)
    
    def process_input(self, user_input):
        """Process the user input"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Processed: {user_input}")
        
        # Handle special commands
        if user_input.lower() == 'time':
            print(f"Current time: {timestamp}")
        elif user_input.lower() == 'status':
            print("System is running normally")
        elif user_input.lower() in ['help', '?']:
            print("Available commands:")
            print("  time   - Show current time")
            print("  status - Show system status")
            print("  help   - Show this help")
            print("  quit   - Exit the program")
        elif user_input.lower() in ['quit', 'exit', 'q']:
            print("Quit command received. Exiting...")
            self.running = False
    
    def input_listener_thread(self):
        """Thread function for listening to input"""
        print("Input thread started")
        
        while self.running:
            try:
                # Non-blocking input check (Unix/Linux only)
                if os.name == 'posix':
                    # Use select to check if input is available
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        user_input = sys.stdin.readline().strip()
                        if user_input:
                            self.process_input(user_input)
                else:
                    # For Windows, use blocking input with timeout
                    try:
                        user_input = input().strip()
                        if user_input:
                            self.process_input(user_input)
                    except EOFError:
                        break
                        
            except Exception as e:
                if self.running:
                    print(f"Input error: {e}")
                break
    
    def background_task(self):
        """Simulate background work"""
        counter = 0
        while self.running:
            counter += 1
            if counter % 10 == 0:  # Print every 10 seconds
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] Background task running... (counter: {counter})")
            time.sleep(1)
    
    def run(self):
        """Main run method"""
        # Register signal handler
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print("Advanced Input Listener Started")
        print("=" * 50)
        print("Features:")
        print("- Continuous background processing")
        print("- Non-blocking input handling")
        print("- Graceful Ctrl-C shutdown")
        print("- Special commands (type 'help' for list)")
        print("=" * 50)
        print("Type commands and press Enter")
        print("Press Ctrl-C to quit gracefully")
        print()
        
        try:
            # Start input listener thread
            self.input_thread = threading.Thread(target=self.input_listener_thread, daemon=True)
            self.input_thread.start()
            
            # Run background task in main thread
            self.background_task()
            
        except KeyboardInterrupt:
            # This shouldn't be reached due to signal handler
            print("\nKeyboard interrupt in main thread")
        finally:
            self.running = False
            print("Main loop ended")

def main():
    """Main function"""
    listener = InputListener()
    listener.run()

if __name__ == "__main__":
    main()
