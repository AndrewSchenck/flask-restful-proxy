# flask-restful-proxy
A slightly more feature-full HTTP Proxy using Flask and Requests.

I've seen some patterns out there for doing request proxying
through flask, but my use-case required something a little
bit more complicated, and this is what I've come up with.

Most HTTP verbs are supported, and an optional JSON payload
can be included, to be passed to the upstream request.

The APIRequestProxy object takes a simple dictionary which
describes a proxy requext, instantiates the
APIRequestProxyUpstream object to create the upstream request,
and provides the results as a Flask Response object two ways.

The status code is set to the result from the upstream request by
default, but this behavior can be disabled by including
'disable_status_passthrough=True' in the proxy_request dictionary.

The response can be stored as an attribute or streamed directly
back to the client (more efficient when fetching large payloads.)

I'm using this behind a REST API, permitting clients to POST
a dictionary describing their proxy request, and passing that
dictionary into APIRequestProxy (see below.) I recommend putting
thought into possible attack vectors / request validation before
implementing this code.


Usage Example 1:

    proxy_request = {
        'url': 'http://www.google.com',
        'method': 'GET',
    }
    proxy = APIRequestProxy()
    proxy.proxy_request = proxy_request
    print(proxy.stream_response())

Usage Example 2:

    proxy_request = {
        'url': 'http://www.my-api-somewhere.com',
        'method': 'POST',
        'disable_status_passthrough': True,
    }
    payload = {
        'some_resource': {...}
    }
    proxy = APIRequestProxy()
    proxy.proxy_request = proxy_request
    proxy.payload = payload
    proxy.make_response()
    return proxy.response
