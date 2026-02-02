import requests

def fetch_item(item):
    try:
        res = requests.get(item.url, timeout=10)
        return res.status_code, res.text
    except Exception as e:
        return None, str(e)
