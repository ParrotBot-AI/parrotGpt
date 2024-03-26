import time

import requests
from sseclient import SSEClient


# Update with the FastAPI SSE endpoint URL


def listen_to_sse():
    try:
        url = 'http://0.0.0.0:8000/v1/modelapi/streaming/'
        response = requests.post(url,
                                 json={
                                     "Ephemeral": "短暂的",
                                     "Serendipity": "意外发现",
                                     "Ubiquitous": "无所不在的",
                                     "Resilient": "有弹性的",
                                     "Conundrum": "难题",
                                 })
        if response.json()['code'] == 10000:
            cliend_id = response.json()['data']['clientId']

        headers = {'Accept': 'text/event-stream'}

        sse_url = f'http://0.0.0.0:8000/v1/modelapi/getVocabContent/{cliend_id}/'
        response = requests.get(sse_url, stream=True, headers=headers)
        if response.status_code == 200:
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith('data:'):
                    data = line[6:]  # Remove the "data: " prefix and any leading/trailing whitespace
                    print(data, end='')  # Decode the binary string properly
                else:
                    print()
                    # time.sleep(0.01)
        else:
            print(f"Error: Server responded with status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")


if __name__ == "__main__":
    listen_to_sse()
