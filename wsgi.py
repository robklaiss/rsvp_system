import sys
sys.path.insert(0, '/home/username/public_html/rsvp_system')

from app import app as application

if __name__ == "__main__":
    application.run()
