#!/bin/bash
# Install gunicorn if not already installed
pip install gunicorn

# Start the application
exec gunicorn app:app
