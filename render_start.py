#!/usr/bin/env python
"""
Render.com startup script
This script ensures gunicorn is installed and starts the Flask application
"""
import os
import sys
import subprocess

def main():
    """Install gunicorn and start the application"""
    # Install gunicorn
    print("Installing gunicorn...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gunicorn"])
    
    # Get the path to gunicorn
    gunicorn_path = subprocess.check_output([sys.executable, "-m", "pip", "show", "-f", "gunicorn"]).decode()
    print(f"Gunicorn info: {gunicorn_path}")
    
    # Start the application using the Python module approach
    print("Starting application with gunicorn...")
    os.execvp(sys.executable, [sys.executable, "-m", "gunicorn", "app:app"])

if __name__ == "__main__":
    main()
