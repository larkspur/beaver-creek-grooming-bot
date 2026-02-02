#!/usr/bin/env python3
"""
Get Facebook Page Access Token for Instagram posting.
"""
import webbrowser
import http.server
import socketserver
import urllib.parse
import requests

APP_ID = "756397747536873"
APP_SECRET = "2a7f9901549f6487351cf2a248a4a10e"
REDIRECT_URI = "http://localhost:8888/callback"
# Only request permissions that are confirmed available
PERMISSIONS = "instagram_content_publish"

# Step 1: Open browser for user to authorize
auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={APP_ID}&redirect_uri={REDIRECT_URI}&scope={PERMISSIONS}&response_type=code"

print("Opening browser for Facebook authorization...")
print("Please log in and authorize the app.\n")
webbrowser.open(auth_url)

# Step 2: Start local server to catch the callback
class CallbackHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Success! You can close this window.</h1></body></html>")
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Error - no code received</h1></body></html>")
        
    def log_message(self, format, *args):
        pass  # Suppress logging

auth_code = None
with socketserver.TCPServer(("", 8888), CallbackHandler) as httpd:
    print("Waiting for authorization callback on http://localhost:8888 ...")
    httpd.handle_request()

if not auth_code:
    print("Failed to get authorization code")
    exit(1)

print("Got authorization code!")

# Step 3: Exchange code for access token
print("\nExchanging code for access token...")
token_url = f"https://graph.facebook.com/v18.0/oauth/access_token"
token_response = requests.get(token_url, params={
    'client_id': APP_ID,
    'client_secret': APP_SECRET,
    'redirect_uri': REDIRECT_URI,
    'code': auth_code
})

token_data = token_response.json()
if 'error' in token_data:
    print(f"Error: {token_data['error']}")
    exit(1)

user_token = token_data['access_token']
print(f"Got user access token!")

# Step 4: Get Page Access Token
print("\nGetting Page access token...")
pages_response = requests.get(
    f"https://graph.facebook.com/v18.0/me/accounts",
    params={'access_token': user_token}
)
pages_data = pages_response.json()

if 'error' in pages_data:
    print(f"Error: {pages_data['error']}")
    exit(1)

print("\nYour Facebook Pages:")
for i, page in enumerate(pages_data.get('data', [])):
    print(f"  {i+1}. {page['name']} (ID: {page['id']})")

if pages_data.get('data'):
    page = pages_data['data'][0]
    page_token = page['access_token']
    page_id = page['id']
    
    # Step 5: Get Instagram Account ID linked to this page
    print(f"\nGetting Instagram account for page '{page['name']}'...")
    ig_response = requests.get(
        f"https://graph.facebook.com/v18.0/{page_id}",
        params={
            'fields': 'instagram_business_account',
            'access_token': page_token
        }
    )
    ig_data = ig_response.json()
    
    if 'instagram_business_account' in ig_data:
        ig_account_id = ig_data['instagram_business_account']['id']
        print(f"\n" + "="*60)
        print("SUCCESS! Add these to your GitHub secrets:")
        print("="*60)
        print(f"\nINSTAGRAM_ACCESS_TOKEN:")
        print(page_token)
        print(f"\nINSTAGRAM_ACCOUNT_ID:")
        print(ig_account_id)
        print("\n" + "="*60)
    else:
        print("No Instagram business account linked to this page.")
        print("Make sure your Instagram is connected to your Facebook Page.")
else:
    print("No pages found. Make sure you have a Facebook Page.")
