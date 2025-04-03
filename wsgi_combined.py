import os
import threading
import logging

# Configure database for Render.com
def configure_render_database():
    """Configure the database URL for Render.com deployment"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Set the SQLAlchemy database URI for both applications
        os.environ['SQLALCHEMY_DATABASE_URI'] = database_url
    
    return database_url

# Configure database
database_url = configure_render_database()

# Import apps after database configuration
from app import main as fastapi_app
from app import app as flask_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('combined_app.log')
    ]
)
logger = logging.getLogger(__name__)

def run_fastapi():
    """Run the FastAPI application in a separate thread"""
    import uvicorn
    port = int(os.environ.get("FASTAPI_PORT", 8000))
    logger.info(f"Starting FastAPI app on port {port}")
    uvicorn.run(fastapi_app.app, host="0.0.0.0", port=port)

# Start FastAPI in a separate thread
fastapi_thread = threading.Thread(target=run_fastapi)
fastapi_thread.daemon = True
fastapi_thread.start()

# The Flask app will be the main application
app = flask_app.app

if __name__ == "__main__":
    # Get the port from the environment variable
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port)
