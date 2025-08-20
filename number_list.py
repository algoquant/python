# Global list to store numbers
numbers = []

def add_number(number):
    """
    Add a number to the global list.
    
    Args:
        number: The number to add to the list
    """
    global numbers
    numbers.append(number)
    print(f"Added {number} to the list. Current list: {numbers}")

def remove_number(number):
    """
    Remove a number from the global list.
    
    Args:
        number: The number to remove from the list
    """
    global numbers
    if number in numbers:
        numbers.remove(number)
        print(f"Removed {number} from the list. Current list: {numbers}")
    else:
        print(f"Number {number} not found in the list. Current list: {numbers}")


# Interactive usage
if __name__ == "__main__":

    print(f"Initial list: {numbers}")
    print("Enter 'a <number>' to add a number, 'r <number>' to remove a number, or 'q' to quit")
    print("Press Ctrl-C to exit")
    
    try:
        while True:
            user_input = input("Enter action and number (e.g., 'a 10' or 'r 5'): ").strip()
            
            if user_input.lower() == 'q':
                print("Goodbye!")
                break
            
            try:
                parts = user_input.split()
                if len(parts) != 2:
                    print("Invalid input. Please use format: 'a 10' or 'r 5'")
                    continue
                
                action = parts[0].lower()
                number = float(parts[1])
                
                if action == 'a':
                    add_number(number)
                elif action == 'r':
                    remove_number(number)
                else:
                    print("Invalid action. Use 'a' to add or 'r' to remove")
            
            except ValueError:
                print("Invalid number. Please enter a valid number.")
            except Exception as e:
                print(f"Error: {e}")
    
    except KeyboardInterrupt:
        print("\nProgram interrupted by user (Ctrl-C)")
    
    print(f"Final list: {numbers}")
