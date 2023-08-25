#!/usr/bin/env python
import requests

file_name = 'example-file-name.txt'

upload_url = '{{ site_url }}{% url "api:upload" %}'
auth = '{{ auth }}'
expire = '{{ expire }}'

headers = {'Authorization': auth, 'Expires-At': expire}

with open(file_name) as file_object:
    files = {'file': (file_name, file_object)}
    r = requests.post(upload_url, headers=headers, files=files)
    r.raise_for_status()

data = r.json()
print(data['url'])
