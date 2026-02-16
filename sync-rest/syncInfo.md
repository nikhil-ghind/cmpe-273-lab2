# CMPE273-01 Week 2 Assignment: Part A Synchronous
Richie Nguyen, 015533661

## Program Notes
- This program tests the synchronous ordering system by sending requests with a `POST /order` call to the ordering service.
- The ordering service then sends a request to the inventory service with a `POST /reserve` call.
- Once the inventory service successfully receives the request from the ordering service, the ordering service then sends a request to the notification service with a `POST /send` call.
- The test program records the latencies of the requests, as well as total and average latency of said requests.
- The test program also shows how many requests were successful and how many requests had errors.
- The testing program includes optional argument `--requests` to specify the amount of requests to send (min = 0, max = 50, default = 1).
- The inventory service also includes optional argument `--delay-time` to specify the amount of seconds to sleep for to simulate a network delay in the system (min = 0, max = 30, default = 0).
- The order service uses localhost:8080, inventory service uses localhost:8081, and notification service uses localhost:8082.

## Installation Instructions
- Run `pip install -r requirements.txt` in a command window at directory `sync-rest`

## Testing Instructions (assuming all requirements are installed)
1. Run `python order.py` in a command window at subdirectory `sync-rest\order_service`
2. Run `python inventory.py <--delay-time T>` in a command window at subdirectory `sync-rest\inventory_service`
	- The argument `--delay-time T` is optional where T is the amount of seconds to sleep for
3. Run `python notification.py` in a command window at subdirectory `sync-rest\notification_service`
4. Run `python testprogram.py <--requests N>` in a command window at subdirectory `sync-rest\tests`
	- The argument `--requests N` is optional where N is the amount of requests
	
## Latency Observations
- Total latency with 1 request and 0s delay: 6.1494s

- Total latency with 1 request and 2s delay: 8.1079s

- Total latency with 5 requests and 0s delay: 30.5529s
- Average latency with 5 requests and 0s delay: 6.1106s

- Total latency with 5 requests and 2s delay: 40.6167s
- Average latency with 5 requests and 2s delay: 8.1233s

- Total latency with 10 requests and 0s delay: 61.0660s
- Average latency with 10 requests and 0s delay: 6.1066s

- Total latency with 10 requests and 2s delay: 80.9850s
- Average latency with 10 requests and 2s delay: 8.0985s

- The two second delay seems to apply to each of the sent requests.
- This means that the total latency is increased by approximately NT seconds where N is the amount of requests and T is the amount of seconds to delay the inventory service by for each request.
- This also means that the average latency is increased by T seconds where T is the amount of seconds to delay the inventory service by for each request.
- Having the compounding time for the total latency shows how synchronous systems are vulnerable to having slower responses if one part of the system is having longer latencies.

## Coding Agent Usage
- The ordering, inventory, notification, and test programs were initially generated with Gemini 3. The programs were then further refined manually.

