#order part for synchronous systems
#initial generation by gemini 3

import logging
import time
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

SERVICE_NAME = "OrderService"
HOST = "localhost"
PORT = 8080
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s',
)

#setting up POST targets with inventory and notification services
INVENTORY_URL = "http://localhost:8081/reserve"
NOTIFICATION_URL = "http://localhost:8082/send"
HEADERS = {"Content-Type": "application/json"}

#health check
@app.route("/health", methods=["GET"])
def health():
    print("running /health check; expected response: status:ok")
    status = "ok"
    return jsonify({"status": status}), 200

#when receiving POST /order
@app.route('/order', methods=['POST'])
def process_order():
    start_time = time.time()#start latency
    
    try:
        # Receive the JSON message
        order_data = request.get_json()
        logger.info(f"Received order {order_data}")
        logger.info(f"Sending {order_data} to InventoryService")
        
        #send order data to inventory; may be affected by inventory latency or availability
        responseInventory = requests.post(INVENTORY_URL, json=order_data, headers=HEADERS, timeout=5)
        if (responseInventory.ok == True):#if inventory call is successful
            logger.info(f"Successfully sent {order_data} to InventoryService")
            logger.info(f"Sending {order_data} to NotificationService")
            responseNotification = requests.post(NOTIFICATION_URL, json = order_data, headers = HEADERS, timeout=5)#send to notification
            if (responseNotification.ok == True):
                logger.info(f"Notification successfully sent")
            else:
                logger.info(f"Error on sending notification")
                responseNotification.raise_for_status()
        else:
            logger.info(f"Error on sending inventory")
            responseInventory.raise_for_status()
    
        # Calculate latency
        latency = time.time() - start_time
        
        # Log service name, endpoint, status, and latency
        logger.info(f"Service: {SERVICE_NAME}, Endpoint: /order, Status: Success, Latency: {latency:.4f}s")
        
        post_order_data = {"POST /order": "success"}
        return jsonify(post_order_data), 200
        
    except Exception as e:#exception if inventory or notification services are unavailable
        latency = time.time() - start_time
        logger.error(f"Service: {SERVICE_NAME}, Endpoint: /order, Status: Error, Latency: {latency:.4f}s")
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Log when the server starts
    logger.info(f"Service: {SERVICE_NAME}, Endpoint: {HOST}:{PORT}, Status: Starting, Latency: N/A")
    app.run(host=HOST, port=PORT)
