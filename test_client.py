import json

from bs4 import BeautifulSoup
from proxy import app


if __name__ == '__main__':
    proxy_request = {
        'proxy_request': {
            'url': 'https://www.google.com',
            'method': 'GET',
            'disable_status_passthrough': False,
        }
    }
    headers = {}
    environment = {}

    with app.test_client() as client:
        methods = {
            'POST':     client.post,
            'PUT':      client.put,
            'GET':      client.get,
            'DELETE':   client.delete,
        }
        response = methods['POST'](
            'http://localhost:5100/proxy/',
            content_type='application/json',
            data=json.dumps(proxy_request),
            headers=headers,
            environ_base=environment,
        )
        soup = BeautifulSoup(response.data,  'html5lib')
        print(soup)
