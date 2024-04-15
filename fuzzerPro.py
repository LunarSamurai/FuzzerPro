import requests
import sys

def loop():
    for word in sys.stdin:
        res = requests.get(url=f"http://10.10.73.89/{word.strip()}")  # Strip whitespace from the word
        if res.status_code == 404:
            print(f"Word '{word.strip()}' not found.")
        elif res.status_code == 200:
            try:
                data = res.json()
                print(data)
            except requests.exceptions.JSONDecodeError:
                print("Response is not valid JSON.")
        else:
            print(f"Unexpected status code: {res.status_code}")

if __name__ == "__main__":
    loop()
