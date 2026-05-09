import argparse
import asyncio
import json
import os
import time

from aiocoap import Code, Context, Message


def build_payload(device_id: str, iteration: int) -> dict[str, object]:
	return {
		"device_id": device_id,
		"metric": "soil_moisture",
		"value": 40 + iteration,
		"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
	}


async def send_once(url: str, payload: dict[str, object]) -> None:
	context = await Context.create_client_context()
	request = Message(code=Code.POST, uri=url, payload=json.dumps(payload).encode("utf-8"))
	response = await context.request(request).response
	print(response.payload.decode("utf-8", errors="replace"))


async def main_async() -> None:
	parser = argparse.ArgumentParser(description="Send telemetry over CoAP")
	parser.add_argument("--url", default=os.getenv("COAP_URL", "coap://localhost:5683/telemetry/coap"))
	parser.add_argument("--device-id", default=os.getenv("DEVICE_ID", "coap-device-1"))
	parser.add_argument("--count", type=int, default=int(os.getenv("COUNT", "1")))
	parser.add_argument("--interval", type=float, default=float(os.getenv("INTERVAL", "2")))
	args = parser.parse_args()

	for iteration in range(args.count):
		payload = build_payload(args.device_id, iteration)
		await send_once(args.url, payload)
		if iteration + 1 < args.count:
			await asyncio.sleep(args.interval)


if __name__ == "__main__":
	asyncio.run(main_async())
