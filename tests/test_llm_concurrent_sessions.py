"""V2.8.0: concurrent expansions from multiple threads must not close
each other's aiohttp session.

The old client kept ONE session and rebuilt it whenever a new event loop
asked for it (article expansion is asyncio.run on a pywebview worker
thread, i.e. a fresh loop per call). Thread 2 therefore closed thread 1's
in-flight session -- reproduced before the fix as "worker1 session closed
while still in use: True" plus "Unclosed client session" at exit.

Each event loop now owns its session and the expansion wrapper closes only
that loop's session. This test drives four real HTTP requests through four
loops/threads against a local stub gateway and checks every reply, the
observed overlap, and that no session is left behind.
"""
import asyncio
import gc
import json
import threading
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.intelligence.gemini_client import GeminiClient

_STATE = {}
_STATE_LOCK = threading.Lock()


class _StubGateway(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        prompt = body["contents"][-1]["parts"][0]["text"]
        with _STATE_LOCK:
            _STATE["active"] += 1
            _STATE["peak"] = max(_STATE["peak"], _STATE["active"])
        try:
            # Hold the request open so the other threads overlap it.
            threading.Event().wait(0.35)
            content = json.dumps({"reply": prompt})
            payload = json.dumps({
                "candidates": [{"content": {"parts": [{"text": content}]}}],
                "usageMetadata": {"totalTokenCount": 3},
            }).encode("utf-8")
        finally:
            with _STATE_LOCK:
                _STATE["active"] -= 1
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # keep pytest output clean
        pass


def test_four_threads_expand_concurrently_without_closing_each_other():
    _STATE.clear()
    _STATE.update({"active": 0, "peak": 0})
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubGateway)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    client = GeminiClient(
        base_url=f"http://127.0.0.1:{port}/v1beta", api_key="test-key", timeout_sec=15.0
    )
    barrier = threading.Barrier(4)
    results = {}
    errors = []

    async def _one(index: int):
        try:
            return await client.chat_json("gemini-3.1-flash-lite", "sys", f"req-{index}")
        finally:
            # Exactly what _run_article_with_cleanup does per expansion.
            await client.close_loop_session()

    def _worker(index: int):
        try:
            barrier.wait(timeout=10)
            results[index] = asyncio.run(_one(index))
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append((index, repr(exc)))

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            workers = [threading.Thread(target=_worker, args=(i,)) for i in range(4)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=30)
            gc.collect()
    finally:
        server.shutdown()
        server.server_close()

    assert not errors, errors
    assert set(results) == {0, 1, 2, 3}
    for index, parsed in results.items():
        assert parsed == {"reply": f"req-{index}"}
    # Proven overlap: at least two requests were inside the gateway at once.
    assert _STATE["peak"] >= 2, _STATE
    # Every loop's session was closed by its own asyncio.run wrapper.
    assert client._sessions == {}
    assert not [
        w for w in caught if "Unclosed client session" in str(w.message)
    ], [str(w.message) for w in caught]
