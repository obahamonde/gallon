"""HTTP client"""
from __future__ import annotations

import http.client
import http.server
import json
import urllib.parse
from typing import Any, Dict, Optional

from .data import dumps
from .objects import Request, Response


class GallonClient:
    """A simple HTTP client"""

    def fetch(self, request: Request):
        """Send a request"""
        parsed_url = urllib.parse.urlparse(request.url)
        conn = self._get_connection(parsed_url)
        headers = self._prepare_headers(request.headers)
        body = self._prepare_body(request)
        if body is None:
            conn.request(request.method, parsed_url.path, headers=headers)
        else:
            if request.method in ("GET", "HEAD"):
                raise ValueError(f"Request method cannot have a body: {request.method}")
            conn.request(request.method, parsed_url.path, body.encode(), headers)

        with conn.getresponse() as res:
            response_headers = self._parse_response_headers(res)
            response_body = self._parse_response_body(res, response_headers)
            response = Response(
                status=res.status, headers=response_headers, body=response_body
            )
            return response.dict()

    def _prepare_body(self, request: Request):
        """Prepare the body based on the content type"""
        body = request.body
        content_type = request.headers.get("content-type", request.content_type)
        if body is None:
            return None
        if isinstance(body, str):
            if content_type == "application/json":
                return dumps(request.json())
            if content_type == "application/x-www-form-urlencoded":
                return self._url_encode_body(json.loads(body))
        if isinstance(body, dict):
            if content_type == "application/json":
                return dumps(body)
            if content_type == "application/x-www-form-urlencoded":
                return self._url_encode_body(body)
            return body
        if isinstance(body, list):
            if content_type == "application/json":
                return dumps(body)
            if content_type == "application/x-www-form-urlencoded":
                return self._url_encode_body(body)
            return body
        return body
    
    def _url_encode_body(self, body: Dict[str, str]) -> str:
        """Encode the body as a URL-encoded string"""
        encoded_params = urllib.parse.urlencode(body)
        return encoded_params

    def get(self, url: str, headers: Optional[Dict[str, str]] = None):
        """Send a GET request to a URL"""
        return self.fetch(Request(method="GET", url=url, headers=headers))

    def post(
        self, url: str, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ):
        """Send a POST request to a URL"""
        return self.fetch(Request(method="POST", url=url, body=body, headers=headers))

    def put(self, url: str, body: Any, headers: Optional[Dict[str, str]] = None):
        """Send a PUT request to a URL"""
        return self.fetch(Request(method="PUT", url=url, body=body, headers=headers))

    def delete(self, url: str, headers: Optional[Dict[str, str]] = None):
        """Send a DELETE request to a URL"""
        return self.fetch(Request(method="DELETE", url=url, body=None, headers=headers))

    def _get_connection(self, parsed_url: urllib.parse.ParseResult):
        """Create an HTTPConnection or HTTPSConnection based on the URL scheme"""
        if parsed_url.scheme == "http":
            return http.client.HTTPConnection(parsed_url.netloc)
        elif parsed_url.scheme == "https":
            return http.client.HTTPSConnection(parsed_url.netloc)
        else:
            raise ValueError(f"Unsupported scheme: {parsed_url.scheme}")

    def _prepare_headers(self, headers: Dict[str, str]):
        """Prepare headers with defaults"""
        prepared_headers = {"User-Agent": "Gallon/0.1"}
        if headers:
            prepared_headers.update(headers)
        return prepared_headers

    def _parse_response_headers(self, response):
        """Parse response headers into a dictionary"""
        return {k.lower(): v for k, v in response.getheaders()}

    def _parse_response_body(self, response, headers):
        """Parse response body based on Content-Type header"""
        content_type = headers.get("content-type", "")
        if "json" in content_type:
            return json.loads(response.read().decode())
        if content_type.startswith("text/"):
            return response.read().decode()
        if content_type.startswith("x-www-form-urlencoded"):
            return urllib.parse.parse_qs(response.read().decode())
        return response.read()
