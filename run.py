"""
Twitch Multi-Account Tool Runner
This script launches the Twitch Multi-Account Tool application.
"""

import os
import sys
import subprocess

def main():
    """Main entry point for the runner script"""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the main.py file
    main_py = os.path.join(script_dir, "src", "main.py")
    
    if not os.path.exists(main_py):
        print(f"Error: Could not find {main_py}")
        print("Please make sure you have the full application downloaded.")
        input("Press Enter to exit...")
        return
    
    try:
        # Execute the main.py file
        subprocess.run([sys.executable, main_py], check=True)
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        print(f"Error running the application: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main() 