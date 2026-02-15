#testing program for synchronous systems
#initial generation by gemini 3

import argparse
import logging
import time
import requests
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define service and endpoint details
SERVICE_NAME = "NormalTest"
URL = "http://localhost:8080/order"
HEADERS = {"Content-Type": "application/json"}

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Send POST /order message to localhost:8080.')
    parser.add_argument('--value', type=str, default="default_value", help='Value for the JSON key parameter')
    args = parser.parse_args()

    PAYLOAD = {"key": args.value}
    
    # Log start of operation
    logger.info(f"Service: {SERVICE_NAME} - Preparing to send POST request to {URL} with payload {PAYLOAD}")

    start_time = time.time()
    try:
        # Send POST request
        response = requests.post(URL, json=PAYLOAD, headers=HEADERS)
        
        # Calculate latency
        latency = time.time() - start_time
        
        # Log the required information: service name, endpoint, status, and latency
        logger.info(f"Service: {SERVICE_NAME}, Endpoint: {URL}, Status: {response.status_code}, Latency: {latency:.4f}s")

    except requests.exceptions.RequestException as e:
        latency = time.time() - start_time
        logger.error(f"Service: {SERVICE_NAME}, Endpoint: {URL}, Status: Failed, Latency: {latency:.4f}s, Error: {e}")

if __name__ == "__main__":
    main()