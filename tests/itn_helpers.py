"""
Test helpers: Transient ITN handler.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from queue import Queue
from typing import Dict, Iterator
from urllib.parse import parse_qs


class PayFastITNHandler(BaseHTTPRequestHandler):
    """
    Minimal ITN callback handler, for testing.

    Expects the server to have a `itn_queue` to put the result to.
    """

    def do_POST(self) -> None:
        assert self.command == 'POST'
        assert self.path == '/'

        # Parse the request body, and post to the queue.
        data = self.read_request_data()
        itn_queue: Queue = self.server.itn_queue  # type: ignore
        itn_queue.put(data)

        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def read_request_body(self) -> str:
        [content_length_str] = self.headers.get_all('Content-Length')
        content_length = int(content_length_str)
        content_bytes = self.rfile.read(content_length)
        content = content_bytes.decode('utf-8')  # XXX
        return content

    def read_request_data(self) -> Dict[str, str]:
        assert self.headers['Content-Type'] == 'application/x-www-form-urlencoded'

        content = self.read_request_body()
        data_lists = parse_qs(
            content,
            # Strict options:
            keep_blank_values=True,
            strict_parsing=True,
            errors='strict',
        )
        # Flatten the listed values.
        data_flat = {k: v for (k, [v]) in data_lists.items()}
        return data_flat


@contextmanager
def itn_handler(host: str, port: int) -> Iterator[Queue]:
    """
    Usage::

        with itn_handler(ITN_HOST, ITN_PORT) as itn_queue:
            # ...complete PayFast payment...
            itn_data = itn_queue.get(timeout=2)
    """
    server_address = (host, port)
    http_server = HTTPServer(server_address, PayFastITNHandler)
    http_server.itn_queue = Queue()  # type: ignore

    executor = ThreadPoolExecutor(max_workers=1)
    executor.submit(http_server.serve_forever)
    try:
        yield http_server.itn_queue  # type: ignore
    finally:
        http_server.shutdown()
