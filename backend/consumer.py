import json
import os
import time

import pika


EXCHANGE_NAME = os.getenv("RABBITMQ_EXCHANGE", "telemetry")
QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "telemetry.backend")
ROUTING_KEY = os.getenv("RABBITMQ_ROUTING_KEY", "sensors.#")


def connection_parameters() -> pika.ConnectionParameters:
	return pika.ConnectionParameters(
		host=os.getenv("RABBITMQ_HOST", "localhost"),
		port=int(os.getenv("RABBITMQ_PORT", "5672")),
		credentials=pika.PlainCredentials(
			os.getenv("RABBITMQ_USER", "guest"),
			os.getenv("RABBITMQ_PASS", "guest"),
		),
		heartbeat=30,
		blocked_connection_timeout=30,
	)


def format_message(body: bytes) -> str:
	try:
		data = json.loads(body.decode("utf-8"))
	except json.JSONDecodeError:
		return body.decode("utf-8", errors="replace")

	return json.dumps(data, indent=2, sort_keys=True)


def run_consumer() -> None:
	while True:
		try:
			connection = pika.BlockingConnection(connection_parameters())
			channel = connection.channel()
			channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
			channel.queue_declare(queue=QUEUE_NAME, durable=True)
			channel.queue_bind(queue=QUEUE_NAME, exchange=EXCHANGE_NAME, routing_key=ROUTING_KEY)

			def on_message(_channel, _method, _properties, body: bytes) -> None:
				print("[backend] message received")
				print(format_message(body))
				print("[backend] ---")
				_channel.basic_ack(delivery_tag=_method.delivery_tag)

			channel.basic_qos(prefetch_count=10)
			channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)
			print(f"[backend] waiting on {QUEUE_NAME} with routing key {ROUTING_KEY}")
			channel.start_consuming()
		except KeyboardInterrupt:
			break
		except Exception as exc:  # noqa: BLE001
			print(f"[backend] reconnecting after error: {exc}")
			time.sleep(2)


if __name__ == "__main__":
	run_consumer()
