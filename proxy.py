"""

This module contains objects for providing a RESTful proxy service;
that is, an HTTP proxy which is controlled via RESTful requests.

The APIRequestProxy object takes a simple dictionary which describes
a proxy requext, instantiates the APIRequestProxyUpstream object to
create the upstream request, and provides the results as a Flask
Response object in one of two ways.

Caching is supported for a limited set of HTTP verbs. The status code
is set to 203 for a cache hit, or passes on the result from the
upstream request for a cache miss. This behavior can be changed by
setting 'disable_status_passthrough=True, but that's probably
something you'd want to do in very limited circumstances.

"""


import requests

from collections import defaultdict
from copy import deepcopy
from time import time

from flask import Flask, request, Response
from werkzeug.exceptions import HTTPException


PROXY_CHUNK_SIZE = 16384
PROXY_METHODS = frozenset(('DELETE', 'GET', 'HEAD', 'OPTIONS', 'PATCH', 'POST', 'PUT'))
PROXY_CACHE_AGE = 5
PROXY_CACHE_METHODS = frozenset(('GET', 'HEAD'))
PROXY_CACHE_STATUS_CODES = frozenset((200, 201, 202, 204))


app = Flask(__name__)


class APIRequestProxyError(Exception):
    """
    Proxy Error
    """
    pass


class CacheMiss(Exception):
    """
    There is no valid cache copy of the object
    """
    pass


class APIRequestProxyUpstream:
    """
    This object creates the upstream request context. If self.payload
    is set, it will be included in the upstream request as JSON.
    """

    def __init__(self):
        self._method = None
        self.url = None
        self.headers = {}
        self.payload = None

    @property
    def method(self) -> str:
        """
        The HTTP request method for the upstream request

        :return: The upstream HTTP request method
        :rtype: str
        """
        return self._method

    @method.setter
    def method(self, value: str) -> None:
        """
        The HTTP request method for the upstream request

        :param value: HTTP request method
        :type value: str
        """
        if value not in PROXY_METHODS:
            raise APIRequestProxyError('Method not supported by proxy: {}'.format(value))

        self._method = value

    def make_request(self, stream=False) -> requests.Response:
        """
        Return the upstream request

        :param stream: Set to True to use streaming mode
        :type stream: bool
        :return: Response from upstream host
        :rtype: requests.Response
        """
        try:
            return requests.request(
                method=self.method,
                url=self.url,
                json=self.payload,
                stream=stream,
                headers=self.headers,
            )
        except requests.RequestException as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    def __str__(self) -> str:
        return self.__class__.__name__

    __repr__ = __str__


class APIRequestProxy:
    """
    This object handles the direction of proxy requests. It will
    instantiate the APIRequestProxyUpstream object, direct it to
    fetch the upstream request, and return the results to the
    application. It supports optional JSON payload and headers,
    which are passed on to the upstream request.
    """

    proxy_request_cache = None
    upstream = None

    @classmethod
    def initialize_cache(cls) -> None:
        """
        Initialize the cache dictionary
        """
        cls.proxy_request_cache = defaultdict(lambda: defaultdict(dict))

    def __init__(self):
        self.response = None
        self._enable_cache = None
        self._cache_age = None
        self._proxy_request = None
        self.headers = {'Content-Type': request.content_type}
        
        self.initialize_cache()

    @property
    def headers(self) -> dict:
        """
        The HTTP headers for the proxy request

        :return: HTTP headers
        :rtype: dict
        """
        try:
            return self.upstream.headers if self.upstream else None
        except AttributeError as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    @headers.setter
    def headers(self, value: dict) -> None:
        """
        The HTTP headers for the proxy request

        :param value: HTTP headers
        :type value: dict
        """
        try:
            if self.upstream:
                self.upstream.headers.update(value)
        except (TypeError, AttributeError) as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    @property
    def method(self) -> str:
        """
        The HTTP verb for the proxy request

        :return: HTTP verb
        :rtype: str
        """
        try:
            return self.upstream.method if self.upstream else None
        except AttributeError as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    @method.setter
    def method(self, value: str) -> None:
        """
        The HTTP verb for the proxy request

        :param value: HTTP verb
        :type value: str
        """
        try:
            if self.upstream:
                self.upstream.method = value
        except AttributeError as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    @property
    def url(self) -> str:
        """
        The URL for the proxy request
        :return: URL
        :rtype: str
        """
        try:
            return self.upstream.url if self.upstream else None
        except AttributeError as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    @url.setter
    def url(self, value: str) -> None:
        """
        The URL for the proxy request

        :param value: URL
        :type value: str
        """
        try:
            if self.upstream:
                self.upstream.url = value
        except AttributeError as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    @property
    def payload(self) -> dict:
        """
        The optional request payload data to be passed on to the
        upstream request as json

        :return: Request payload
        :rtype: dict
        """
        try:
            return self.upstream.payload if self.upstream else None
        except AttributeError as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    @payload.setter
    def payload(self, value: dict) -> None:
        """
        The data value of the payload is passed upstream, while
        the meta value controls our own behavior

        :param value: Request payload data
        :type value: dict
        """
        try:
            self.upstream.payload = value.get('data')
            self.proxy_request = value['meta']['proxy_request']
        except (KeyError, TypeError, AttributeError) as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    @property
    def enable_cache(self) -> bool:
        """
        True if request caching is enabled

        :return: True if request caching is enabled
        :rtype: bool
        """
        return self._enable_cache

    @enable_cache.setter
    def enable_cache(self, value: bool) -> None:
        """
        True if request caching is enabled

        :param value: enable_cache
        :type value: bool
        """
        self._enable_cache = value if self.method in PROXY_CACHE_METHODS else False

    @property
    def cache_age(self) -> int:
        """
        If request caching is being used, the time in seconds to
        cache the object

        :return: Request cache timer, in seconds
        :rtype: int
        """
        return self._cache_age

    @cache_age.setter
    def cache_age(self, value: int) -> None:
        """
        If request caching is being used, the time in seconds to
        cache the object

        :param value: The time to cache the response
        :type value: int
        """
        self._cache_age = value if value >= 0 else PROXY_CACHE_AGE

    @property
    def proxy_request(self) -> dict:
        """
        A dictionary describing the upstream request to proxy

        :return:
        :rtype:
        :return: Request to proxy
        :rtype: dict
        """
        return self._proxy_request

    @proxy_request.setter
    def proxy_request(self, value: dict) -> None:
        """
        A dictionary describing the upstream request to proxy

        :param value: Request to proxy
        :type value: dict
        """
        try:
            self.method = value['method']
            self.url = value['url']

            self.headers = value.get('headers', {})
            self.enable_cache = value.get('enable_cache', False)
            self.cache_age = value.get('cache_age', PROXY_CACHE_AGE)

            if value.get('initialize_cache') is True:
                self.initialize_cache()

            self._proxy_request = value

        except (KeyError, TypeError, AttributeError) as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    @property
    def chunk_size(self) -> int:
        """
        When in streaming mode, the size of the generator buffer

        :return: Streaming chunk size
        :rtype: int
        """
        return self.proxy_request.get('chunk_size', PROXY_CHUNK_SIZE)

    @property
    def status_passthrough(self) -> bool:
        """
        If True, instead of passing through HTTP status as received
        from the upstream, we set the status code ourselves (only
        applies to 2XX codes)

        :return: True to set status, False to pass on the 'real'
                 status
        :rtype: bool
        """
        return not self.proxy_request.get('disable_status_passthrough')

    def response_from_upstream(self) -> Response:
        """
        Open an upstream request and return the resulting Response

        :return: Response from upstream
        :rtype: Response
        """
        try:
            upstream_request = self.upstream.make_request()
            response = Response(
                response=upstream_request.content,
                content_type=upstream_request.headers.get('Content-Type'),
                status=upstream_request.status_code if self.status_passthrough else 203,
            )
            return response
        except (HTTPException, AttributeError) as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    def response_from_cache(self) -> Response:
        """
        Fetch the requested Response from cache, if valid, otherwise
        fall back to making an upstream request

        :return: Response from upstream
        :rtype: Response
        """
        try:
            if time() < self.proxy_request_cache[self.method][self.url]['expire']:
                response = deepcopy(self.proxy_request_cache[self.method][self.url]['response'])
                response.status_code = 203
            else:
                raise CacheMiss('Object expired from cache')
        except (KeyError, CacheMiss):
            response = self.response_from_upstream()
            if response.status_code in PROXY_CACHE_STATUS_CODES:
                self.proxy_request_cache[self.method][self.url] = {
                    'response': response,
                    'expire':   time() + self.cache_age,
                }
        return response

    def make_response(self) -> None:
        """
        Create a response out of the results from the upstream
        request
        """
        if self.enable_cache is True:
            self.response = self.response_from_cache()
        else:
            self.response = self.response_from_upstream()

    def stream_response(self) -> Response:
        """
        Streaming mode -- stream the upstream request through to the
        client using an iterator, enabling efficient fetching of
        larger payloads

        :return: The response from the upstream
        :rtype: Response
        """
        try:
            upstream_request = self.upstream.make_request(stream=True)
            return Response(
                response=upstream_request.iter_content(chunk_size=self.chunk_size),
                content_type=upstream_request.headers.get('Content-Type'),
                status=upstream_request.status_code if self.status_passthrough else 203,
            )
        except HTTPException as e:
            raise APIRequestProxyError('Proxy Error: {}'.format(str(e))) from e

    def __str__(self) -> str:
        return self.__class__.__name__

    __repr__ = __str__


@app.route('/proxy/', methods=['POST'])
def flask_restful_proxy():
    proxy = APIRequestProxy()
    proxy.payload = request.json
    proxy.make_response()
    return proxy.response


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5100,
        debug=True,
        threaded=True,
    )
