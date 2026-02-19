#inventory part for synchronous systems
#initial generation by gemini 3

import logging
import time
from flask import Flask, request, jsonify
import requests
import argparse

app = Flask(__name__)

SERVICE_NAME = "InventoryService"
HOST = "localhost"
PORT = 8081
DELAY_TIME = 0#default delay time, changed by optional input argument
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s',
)

#health check
@app.route("/health", methods=["GET"])
def health():
    print("running /health check; expected response: status:ok")
    status = "ok"
    return jsonify({"status": status}), 200

#set delay time from a get call
@app.route("/set-delay-time", methods=["GET"])
def setDelayTime():
    #print("setting delay time")
    inputDelayTime = request.args.get("delay-time", "")
    #print("delay time: " + str(inputDelayTime))
    try:
        DELAY_TIME = int(inputDelayTime)
        return jsonify({"New delay time": DELAY_TIME}), 200
    except Exception as e:
        return jsonify({"Error on setting delay time": str(e)}), 500


#POST /reserve from order
@app.route('/reserve', methods=['POST'])
def process_reserve():
    start_time = time.time()
    
    logger.info(f"Simulating delay for {DELAY_TIME} seconds")
    time.sleep(DELAY_TIME)
    
    try:
        # Receive the JSON message
        reserve_data = request.get_json()
        logger.info(f"Received order {reserve_data}")
        
        # Calculate latency
        latency = time.time() - start_time
        
        # Log service name, endpoint, status, and latency
        logger.info(f"Service: {SERVICE_NAME}, Endpoint: /reserve, Status: Success, Latency: {latency:.4f}s")
        
        post_reserve_data = {"POST /reserve": "success"}
        return jsonify(post_reserve_data), 200
        
    except Exception as e:
        latency = time.time() - start_time
        logger.error(f"Service: {SERVICE_NAME}, Endpoint: /reserve, Status: Error, Latency: {latency:.4f}s")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    #set up delay for testing
    parser = argparse.ArgumentParser(description='Test network delay for synchronous systems (minimum = 0, maximum = 30, default = 0)')
    parser.add_argument(
        "--delay-time",
        type=int,
        default="0",
        help='Amount of seconds to wait before processing order request (minimum = 0, maximum = 30, default = 0)')
    args = parser.parse_args()
    if (args.delay_time < 0):
        parser.error("Delay time must be at least 0 seconds")
    elif (args.delay_time > 30):
        parser.error("Delay time must be at most 30 seconds")
    DELAY_TIME = args.delay_time#changing default delay time to input value
    logger.info(f"Delay time has been set to {DELAY_TIME} seconds")
    
    # Log when the server starts
    logger.info(f"Service: {SERVICE_NAME}, Endpoint: {HOST}:{PORT}, Status: Starting, Latency: N/A")
    app.run(host=HOST, port=PORT)

