# flask-restful-proxy
A caching / streaming HTTP Proxy using Flask and Requests.

I've seen some patterns out there for doing request proxying
through Flask, but my use-case required something a little
bit more complicated, and this is what I've come up with.

The APIRequestProxy object takes a simple dictionary which
describes a proxy requext, instantiates the upstream object to
create the upstream request, and provides the results as a
Flask Response object.

Most HTTP verbs are supported, and an optional JSON payload
can be included -- stick it inside a key named 'data' inside
the proxy_request dictionary.

A primitive caching implementation is included, but disabled
by default. The fields 'enable_cache' and 'cache_age' control
the response caching behavior.

The status code is set to the result from the upstream request by
default, but this behavior can be disabled by including
'disable_status_passthrough=True' in the proxy_request dictionary.

The response can be stored as an attribute or streamed directly
back to the client (more efficient when fetching large payloads.)

I recommend putting careful thought into possible attack vectors
and input validation before implementing this code.


Usage Example 1:

    proxy_request = {
        'url': 'http://some_valid_url',
        'method': 'POST',
    }
    proxy = APIRequestProxy()
    proxy.proxy_request = proxy_request
    print(proxy.stream_response())

Usage Example 2:

    proxy_request = {
        'url': 'http://www.google.com',
        'method': 'GET',
        'enable_cache': True,
        'cache_age': 5,

    }
    payload = {
        'some_resource': {...}
    }
    proxy = APIRequestProxy()
    proxy.proxy_request = proxy_request
    proxy.payload = payload
    proxy.make_response()
    return proxy.response
