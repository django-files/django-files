#!/usr/bin/env python
import requests

file_name = 'example-file-name.txt'

site_url = '{{ site_url }}'
auth = '{{ auth }}'
expire = '{{ expire }}'

url = site_url + '/upload'
headers = {'Authorization': auth, 'ExpiresAt': expire}

with open(file_name) as file_object:
    files = {'file': (file_name, file_object)}
    r = requests.post(url, headers=headers, files=files)
    r.raise_for_status()

print(r.json()['url'])
