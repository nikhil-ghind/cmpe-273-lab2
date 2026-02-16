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

ORDER_URL = "http://localhost:8080/order"
HEADERS = {"Content-Type": "application/json"}
REQUEST_AMOUNT = 1#default amount of requests to send

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Send POST /order request to localhost:8080.')
    parser.add_argument(
        "--requests",
        type=int,
        default="1",
        help='Amount of requests to send (minimum = 0, maximum = 50, default = 1)')
    args = parser.parse_args()
    if (args.requests < 0):
        parser.error("Amount of requests must be at least 0")
    elif (args.requests > 50):
        parser.error("Amount of requests must be at most 50")
    REQUEST_AMOUNT = args.requests
    
    logger.info(f"Sending {REQUEST_AMOUNT} requests to {ORDER_URL}")
    totalLatency = 0
    avgLatency = 0#stats for latency

    counter = 0
    successfulRequests = 0
    errorRequests = 0
    while (counter < REQUEST_AMOUNT):#repeating requests until specified amount is sent
        orderValue = "test #" + str(counter + 1)
        order = {"order": orderValue}
        localLatencyStart = time.time()#local latency per request
        response = requests.post(ORDER_URL, json=order, headers=HEADERS)
        localLatency = time.time() - localLatencyStart#calculate local latency
        logger.info(f"Sent request {counter + 1} with status {response.status_code} and latency {localLatency:.4f}s")
        if (response.ok == True):
            successfulRequests += 1
        else:
            errorRequests += 1
        totalLatency += localLatency#adding to total latency
        counter += 1
        
    #logging latency stats
    logger.info(f"Total latency after sending {REQUEST_AMOUNT} requests: {totalLatency:.4f}s")
    if (REQUEST_AMOUNT > 0):#calculate average latency if at least 1 request is sent
        avgLatency = (totalLatency / REQUEST_AMOUNT)
    logger.info(f"Average latency after sending {REQUEST_AMOUNT} requests: {avgLatency:.4f}s")
    logger.info(f"Successful requests: {successfulRequests}")
    logger.info(f"Errored requests: {errorRequests}")


if __name__ == "__main__":
    main()