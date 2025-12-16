import os
import requests
import json
import importlib.util

def _ensure_api_key():
    """Get API key from environment or secrets_local.py"""
    key = os.environ.get('GEMINI_KEY')
    if key: return key
    try:
        spec = importlib.util.find_spec('secrets_local')
        if spec:
            secrets_local = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(secrets_local)
            return getattr(secrets_local, 'GEMINI_KEY', None)
    except: pass
    return None

def test_api():
    print("--- DIAGNOSTIC START ---")
    key = _ensure_api_key()
    if not key:
        print("ERROR: No API Key found.")
        return

    print(f"API Key found: {key[:5]}...")

    # We will try a few variations to see which one gives a clue
    # 1. Standard correct URL
    model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": "Hello"}]}]}
    
    print(f"\n[Test 1] Trying standard URL for {model}:")
    print(f"URL: {url.replace(key, 'KEY_HIDDEN')}")
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

    # 2. List models (this usually works even if generateContent fails)
    url_list = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    print(f"\n[Test 2] Listing available models:")
    try:
        response = requests.get(url_list, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            models = response.json().get('models', [])
            names = [m['name'] for m in models]
            print(f"Available Models: {names}")
            if not names:
                print("No models returned. API Key might be invalid or project has no access.")
        else:
            print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

    print("--- DIAGNOSTIC END ---")

if __name__ == "__main__":
    test_api()
