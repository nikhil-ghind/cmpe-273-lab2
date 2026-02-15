#inventory part for synchronous systems
#initial generation by gemini 3

import logging
import time
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

SERVICE_NAME = "InventoryService"
HOST = "localhost"
PORT = 8081
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

@app.route('/reserve', methods=['POST'])
def process_reserve():
    start_time = time.time()
    
    try:
        # Receive the JSON message
        reserve_data = request.get_json()
        
        #placeholder for POST /reserve part
        # Send POST /reserve to localhost:8081 with the same JSON field
        ##requests.post("http://localhost:8081/reserve", json=order_data)

        # test
        logger.info(f"received order {reserve_data}")
        notification_data = {"notify": "success"}
        
        #placeholder for POST /send part
        # When the program receives a message from localhost:8081 (synchronous return above)
        # Send POST /send to localhost:8082 with {"notify":"success"}
        ##notification_data = {"notify": "success"}
        ##requests.post("http://localhost:8082/send", json=notification_data)
        
        # Calculate latency
        latency = time.time() - start_time
        
        # Log service name, endpoint, status, and latency
        logger.info(f"Service: {SERVICE_NAME}, Endpoint: /order, Status: Success, Latency: {latency:.4f}s")
        
        return jsonify(notification_data), 200
        
    except Exception as e:
        latency = time.time() - start_time
        logger.error(f"Service: {SERVICE_NAME}, Endpoint: /order, Status: Error, Latency: {latency:.4f}s")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Log when the server starts
    logger.info(f"Service: {SERVICE_NAME}, Endpoint: localhost:8081, Status: Starting, Latency: N/A")
    app.run(host=HOST, port=PORT)
