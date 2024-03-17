import time

import requests
from sseclient import SSEClient

# Update with the FastAPI SSE endpoint URL
sse_url = 'http://0.0.0.0:8000/v1/modelapi/assistantChatbot/'

def listen_to_sse(url):
    try:
        headers = {'Accept': 'text/event-stream'}
        response = requests.post(url,
                json={
                    "queryType": "a",
                    "chatbotQuery": "Write me a poem about the TOEFL exam",
                    "passage": "a",
                    "mcq": "a",
                },
                stream=True,
                headers=headers)
        if response.status_code == 200:
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith('data:'):
                    data = line[5:].strip()  # Remove the "data: " prefix and any leading/trailing whitespace
                    print("Data:", data)  # Decode the binary string properly
                    time.sleep(0.05)
        else:
            print(f"Error: Server responded with status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")


if __name__ == "__main__":
    listen_to_sse(sse_url)