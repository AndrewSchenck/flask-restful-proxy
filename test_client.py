import json

from bs4 import BeautifulSoup
from wut import app


if __name__ == '__main__':
    payload = {
        'meta': {
            'proxy_request': {
                'url': 'https://www.google.com',
                'method': 'GET',
                'enable_cache': True,
                'cache_age': 5,

            }
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
            data=json.dumps(payload),
            headers=headers,
            environ_base=environment,
        )
        soup = BeautifulSoup(response.data,  'html5lib')
        print(soup)
