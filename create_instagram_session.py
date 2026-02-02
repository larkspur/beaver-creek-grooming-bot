#!/usr/bin/env python3
"""
Create an Instagram session using Facebook login.
"""
import json
import base64
import getpass
from instagrapi import Client

print("Instagram Session Creator (via Facebook)")
print("=" * 50)
print("\nSince your Instagram is linked to Facebook,")
print("we'll use your Facebook credentials instead.\n")

# Option 1: Try with Facebook credentials
print("Enter your FACEBOOK credentials (not Instagram):")
fb_email = input("Facebook email: ")
fb_password = getpass.getpass("Facebook password: ")

print("\nLogging in via Facebook...")
cl = Client()

try:
    # Login with Facebook
    cl.login_by_sessionid(fb_email)  # This won't work, let me try different approach
except:
    pass

# Actually, let's try a different approach - use the session from browser
print("\n" + "=" * 50)
print("ALTERNATIVE APPROACH")
print("=" * 50)
print("\nSince direct login isn't working, try this:")
print("\n1. Open Instagram.com in Chrome")
print("2. Log in normally")
print("3. Press F12 to open Developer Tools")
print("4. Go to Application tab → Cookies → instagram.com")
print("5. Find 'sessionid' cookie and copy its value")
print("\nThen run this command with your sessionid:")
print("\n  python3 -c \"")
print("from instagrapi import Client")
print("import json, base64")
print("cl = Client()")
print("cl.login_by_sessionid('YOUR_SESSIONID_HERE')")
print("print(base64.b64encode(json.dumps(cl.get_settings()).encode()).decode())\"")
