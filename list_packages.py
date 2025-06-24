# List all the packages loaded in the current Python session.

import sys

# Get a dictionary of all loaded modules
loaded_modules = sys.modules

# Iterate and print the module names
print("Loaded modules:")
for module_name in loaded_modules:
    print(module_name) 

