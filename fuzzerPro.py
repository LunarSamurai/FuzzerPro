import requests
import sys


def loop():
    for word in sys.stdin:
        res = requests.get(url=f"http://10.10.212.140/{word}")
        if res.status_code == 404:
            loop()
        else:
            data = res.json()
            print(data)
            print(res.status_code)
            print(word)
        # data = res.json()
        # print(data)
loop()