# test_auth.py
import requests

BASE_URL = "http://127.0.0.1:8000"  # Change if your server runs on a different URL

def test_auth_flow():
    # 1. Login to get the token
    login_data = {
        "email": "gamingsimo40@gmail.com",
        "password": "12345678"
    }
    login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print("Login Response:", login_response.json())
    
    if login_response.status_code != 200:
        print(f"Login failed with status code {login_response.status_code}")
        return
    
    token = login_response.json().get("access_token")
    
    # 2. Test the /me endpoint with various header formats
    headers = {
        "Authorization": f"Bearer {token}"
    }
    me_response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print("\nMe Response (Standard):", me_response.status_code, me_response.text)
    
    # Try with lowercase header name
    headers = {
        "authorization": f"Bearer {token}"
    }
    me_response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print("\nMe Response (lowercase header):", me_response.status_code, me_response.text)
    
    # Try with different spacing
    headers = {
        "Authorization": f"Bearer{token}"  # No space after Bearer
    }
    me_response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print("\nMe Response (no space):", me_response.status_code, me_response.text)
    
    # Debug print all request headers
    headers = {
        "Authorization": f"Bearer {token}"
    }
    print("\nRequest Headers:", headers)
    

if __name__ == "__main__":
    test_auth_flow()