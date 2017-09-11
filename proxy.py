"""

This module contains objects for providing a RESTful proxy service.
This is meant to be called from inside a Flask instance, to provide
upstream HTTP service to clients.

The response can be stored as an attribute or streamed directly
back to the client (more efficient when fetching large payloads.)

"""


import requests
from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException

app = Flask(__name__)


class APIRequestProxyError(Exception):
    """Exception class for Proxy Errors"""
    pass


class APIRequestProxyUpstream:
    """
    This object creates the upstream request context. If self.payload
    is set, it will be included in the upstream request as JSON.
    """

    def __init__(self):
        self._method = None
        self.request = None
        self.url = None
        self.headers = None
        self.payload = None
        self.request_method = None

    @property
    def method(self) -> str:
        """
        The HTTP request method for the upstream request

        :return: The upstream HTTP request method
        :rtype: str
        """
        return self._method

    @method.setter
    def method(self, value) -> None:
        """
        Map the HTTP request method to the appropriate object

        :param value: The HTTP request method
        :type value: str
        :return: None
        :rtype: None
        """
        request_methods = {
            'DELETE':   requests.delete,
            'GET':      requests.get,
            'HEAD':     requests.head,
            'OPTIONS':  requests.options,
            'PATCH':    requests.patch,
            'POST':     requests.post,
            'PUT':      requests.put,
        }
        try:
            self.request_method = request_methods[value]
        except KeyError as e:
            raise APIRequestProxyError('Unsupported Proxy Method') from e

        self._method = value

    def make_request(self, stream=False) -> None:
        """
        Form the upstream request

        :param stream: Set to True to use streaming mode
        :type stream: bool
        """
        try:
            self.request = self.request_method(
                url=self.url,
                json=self.payload,
                stream=stream,
                headers=self.headers,
            )
        except requests.RequestException as e:
            raise APIRequestProxyError('Proxy Error') from e

    def __str__(self) -> str:
        return __class__.__name__

    __repr__ = __str__


class APIRequestProxy:
    """
    This object handles the direction of proxy requests.
    It will instantiate the APIRequestProxyUpstream object,
    direct it to fetch the upstream request, and return
    the results to the application. It supports optional
    JSON payload and headers, which are passed on to the
    upstream request.
    """

    def __init__(self, proxy_request=None, payload=None):
        self._proxy_request = None
        self._payload = None
        self.response = None
        self.status_passthrough = True
        self.upstream = APIRequestProxyUpstream()
        self.proxy_request = proxy_request
        self.payload = payload

    @property
    def proxy_request(self) -> dict:
        """
        The proxy_request field out of the payload metadata

        :return: The proxy_request metadata
        :rtype: dict
        """
        return self._proxy_request

    @proxy_request.setter
    def proxy_request(self, value) -> None:
        """
        As we set proxy_request, we pull some values out of it
        and assign them to attributes inside of the upstream
        object.

        :param value: proxy_request definition
        :type value: dict
        """
        upstream_headers = {'Content-Type': request.content_type}

        try:
            if 'headers' in value:
                upstream_headers.update(value['headers'])
            self.upstream.headers = upstream_headers

            if value.get('disable_status_passthrough'):
                self.status_passthrough = False

            self.upstream.method = value['method']
            self.upstream.url = value['url']
        except KeyError as e:
            raise APIRequestProxyError('Proxy Error') from e

        self._proxy_request = value

    @property
    def payload(self) -> dict:
        """
        The optional request payload data to be passed on to the
        upstream request as json

        :return: Request payload
        :rtype: dict
        """
        return self.upstream.payload

    @payload.setter
    def payload(self, value) -> None:
        """
        The payload is stored inside the upstream object

        :param value: Request payload data
        :type value: dict
        """
        self.upstream.payload = value

    @property
    def response_params(self) -> dict:
        """
        The base parameters to be passed into the Response object

        :return: Response parameters
        :rtype: dict
        """
        return {
            'content_type': self.upstream.request.headers.get('Content-Type'),
            'status':       self.upstream.request.status_code if self.status_passthrough else 200
        }

    def make_response(self) -> None:
        """
        Create a response out of the results from the upstream
        request
        """
        try:
            self.upstream.make_request()
            content = dict(response=self.upstream.request.content)
            self.response = Response(**content, **self.response_params)
        except HTTPException as e:
            raise APIRequestProxyError('Proxy Error') from e

    def stream_response(self) -> Response:
        """
        Streaming mode -- stream the upstream request through to the
        client using an iterator, enabling efficient fetching of larger
        payloads

        :return: The response from the upstream
        :rtype: Response
        """
        try:
            self.upstream.make_request(stream=True)
            content = dict(response=self.upstream.request.iter_content(chunk_size=16384))
            return Response(**content, **self.response_params)
        except HTTPException as e:
            raise APIRequestProxyError('Proxy Error') from e

    def __str__(self) -> str:
        return __class__.__name__

    __repr__ = __str__


@app.route('/proxy/', methods=['POST'])
def flask_restful_proxy():
    proxy_request = request.json.get('proxy_request')
    proxy = APIRequestProxy(proxy_request=proxy_request)
    return proxy.stream_response()


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5100,
        debug=True,
        threaded=True,
    )
