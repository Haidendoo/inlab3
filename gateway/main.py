import asyncio
import json
import os
from datetime import datetime, timezone

import pika
from aiohttp import web
from aiocoap import Code, Context, Message, resource


EXCHANGE_NAME = os.getenv("RABBITMQ_EXCHANGE", "telemetry")
ROUTING_PREFIX = os.getenv("ROUTING_PREFIX", "sensors")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")


def now_iso() -> str:
	return datetime.now(timezone.utc).isoformat()


def normalize_payload(protocol: str, incoming: dict[str, object], routing_key: str) -> dict[str, object]:
	device_id = str(incoming.get("device_id", f"{protocol}-device"))
	metric = str(incoming.get("metric", "telemetry"))
	value = incoming.get("value")

	return {
		"device_id": device_id,
		"protocol": protocol,
		"metric": metric,
		"value": value,
		"timestamp": incoming.get("timestamp", now_iso()),
		"source_ip": incoming.get("source_ip"),
		"routing_key": routing_key,
	}


def publish_message(message: dict[str, object], routing_key: str) -> None:
	connection = pika.BlockingConnection(
		pika.ConnectionParameters(
			host=RABBITMQ_HOST,
			port=RABBITMQ_PORT,
			credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
			heartbeat=30,
			blocked_connection_timeout=30,
		)
	)
	try:
		channel = connection.channel()
		channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
		channel.basic_publish(
			exchange=EXCHANGE_NAME,
			routing_key=routing_key,
			body=json.dumps(message).encode("utf-8"),
			properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
		)
	finally:
		connection.close()


async def publish_async(message: dict[str, object], routing_key: str) -> None:
	await asyncio.to_thread(publish_message, message, routing_key)


async def handle_http_telemetry(request: web.Request) -> web.Response:
	try:
		incoming = await request.json()
	except Exception:  # noqa: BLE001
		incoming = {"raw": await request.text()}

	if not isinstance(incoming, dict):
		incoming = {"value": incoming}

	message = normalize_payload("http", incoming, f"{ROUTING_PREFIX}.http")
	message["source_ip"] = request.remote
	await publish_async(message, f"{ROUTING_PREFIX}.http")
	return web.json_response({"status": "stored", "message": message})


class CoapTelemetryResource(resource.Resource):
	async def render_post(self, request: Message) -> Message:
		try:
			incoming = json.loads(request.payload.decode("utf-8")) if request.payload else {}
		except json.JSONDecodeError:
			incoming = {"raw": request.payload.decode("utf-8", errors="replace")}

		if not isinstance(incoming, dict):
			incoming = {"value": incoming}

		message = normalize_payload("coap", incoming, f"{ROUTING_PREFIX}.coap")
		await publish_async(message, f"{ROUTING_PREFIX}.coap")
		return Message(code=Code.CHANGED, payload=json.dumps({"status": "stored", "message": message}).encode("utf-8"))


async def health(request: web.Request) -> web.Response:
	return web.json_response({"status": "ok"})


async def start_coap_server() -> Context:
	site = resource.Site()
	site.add_resource(["telemetry", "coap"], CoapTelemetryResource())
	return await Context.create_server_context(site, bind=("0.0.0.0", 5683))


async def start_http_server() -> web.AppRunner:
	app = web.Application()
	app.router.add_get("/health", health)
	app.router.add_post("/telemetry/http", handle_http_telemetry)

	runner = web.AppRunner(app)
	await runner.setup()
	site = web.TCPSite(runner, "0.0.0.0", 8080)
	await site.start()
	return runner


async def main() -> None:
	await start_http_server()
	await start_coap_server()
	print("[gateway] HTTP on :8080, CoAP on :5683")
	await asyncio.Event().wait()


if __name__ == "__main__":
	asyncio.run(main())
