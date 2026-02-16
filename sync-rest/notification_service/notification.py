#notification part for synchronous systems
#initial generation by gemini 3

import logging
import time
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

SERVICE_NAME = "NotificationService"
HOST = "localhost"
PORT = 8082
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

#POST /send from order after inventory reserve
@app.route('/send', methods=['POST'])
def process_notification():
    start_time = time.time()
    
    try:
        # Receive the JSON message
        notification_data = request.get_json()
        logger.info(f"Received order {notification_data}")
        
        # Calculate latency
        latency = time.time() - start_time
        
        # Log service name, endpoint, status, and latency
        logger.info(f"Service: {SERVICE_NAME}, Endpoint: /send, Status: Success, Latency: {latency:.4f}s")
        
        post_send_data = {"POST /send": "success"}
        return jsonify(post_send_data), 200
        
    except Exception as e:
        latency = time.time() - start_time
        logger.error(f"Service: {SERVICE_NAME}, Endpoint: /send, Status: Error, Latency: {latency:.4f}s")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Log when the server starts
    logger.info(f"Service: {SERVICE_NAME}, Endpoint: {HOST}:{PORT}, Status: Starting, Latency: N/A")
    app.run(host=HOST, port=PORT)
