import argparse
import json
import os
import socket
from urllib.parse import urlparse
import time


def build_payload(device_id: str, iteration: int) -> dict[str, object]:
	return {
		"device_id": device_id,
		"metric": "temperature",
		"value": 20 + iteration,
		"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
	}


def send_once(url: str, payload: dict[str, object]) -> None:
	parsed = urlparse(url)
	host = parsed.hostname or "localhost"
	port = parsed.port or 80
	path = parsed.path or "/"
	body = json.dumps(payload)

	request_text = (
		f"POST {path} HTTP/1.1\r\n"
		f"Host: {host}:{port}\r\n"
		"Content-Type: application/json\r\n"
		f"Content-Length: {len(body.encode('utf-8'))}\r\n"
		"Connection: close\r\n\r\n"
		f"{body}"
	)

	with socket.create_connection((host, port), timeout=10) as connection:
		connection.sendall(request_text.encode("utf-8"))
		response = bytearray()
		while True:
			chunk = connection.recv(4096)
			if not chunk:
				break
			response.extend(chunk)

	print(response.decode("utf-8", errors="replace"))


def main() -> None:
	parser = argparse.ArgumentParser(description="Send telemetry over HTTP")
	parser.add_argument("--url", default=os.getenv("GATEWAY_HTTP_URL", "http://localhost:8080/telemetry/http"))
	parser.add_argument("--device-id", default=os.getenv("DEVICE_ID", "http-device-1"))
	parser.add_argument("--count", type=int, default=int(os.getenv("COUNT", "1")))
	parser.add_argument("--interval", type=float, default=float(os.getenv("INTERVAL", "2")))
	args = parser.parse_args()

	for iteration in range(args.count):
		payload = build_payload(args.device_id, iteration)
		try:
			send_once(args.url, payload)
		except OSError as exc:
			print(f"http send failed: {exc}")
			raise SystemExit(1) from exc
		if iteration + 1 < args.count:
			time.sleep(args.interval)


if __name__ == "__main__":
	main()
