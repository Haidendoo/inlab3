import argparse
import json
import os
import sys
import time
from pathlib import Path


# Running this file directly adds ./device to sys.path, which can shadow
# stdlib modules like http via device/http.py. Remove that path first.
SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR in sys.path:
	sys.path.remove(SCRIPT_DIR)

import paho.mqtt.client as mqtt


def build_payload(device_id: str, iteration: int) -> str:
	return json.dumps(
		{
			"device_id": device_id,
			"protocol": "mqtt",
			"metric": "humidity",
			"value": 55 + iteration,
			"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
		}
	)


def main() -> None:
	parser = argparse.ArgumentParser(description="Publish telemetry over MQTT")
	parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
	parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
	parser.add_argument("--topic", default=os.getenv("MQTT_TOPIC", "sensors.mqtt"))
	parser.add_argument("--device-id", default=os.getenv("DEVICE_ID", "mqtt-device-1"))
	parser.add_argument("--count", type=int, default=int(os.getenv("COUNT", "1")))
	parser.add_argument("--interval", type=float, default=float(os.getenv("INTERVAL", "2")))
	args = parser.parse_args()

	client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
	client.username_pw_set(os.getenv("MQTT_USER", "guest"), os.getenv("MQTT_PASS", "guest"))
	client.connect(args.host, args.port, keepalive=30)
	client.loop_start()

	try:
		for iteration in range(args.count):
			payload = build_payload(args.device_id, iteration)
			info = client.publish(args.topic, payload=payload, qos=1)
			info.wait_for_publish()
			print(f"published to {args.topic}: {payload}")
			if iteration + 1 < args.count:
				time.sleep(args.interval)
	finally:
		client.loop_stop()
		client.disconnect()


if __name__ == "__main__":
	main()
