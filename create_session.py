#!/usr/bin/env python3
"""
Run this script locally to create an Instagram session.
The session can then be used in GitHub Actions.
"""
from instagrapi import Client
import getpass

print("Instagram Session Creator")
print("=" * 40)

username = input("Enter your Instagram username: ")
password = getpass.getpass("Enter your Instagram password: ")

print("\nLogging in...")
cl = Client()

try:
    cl.login(username, password)
    cl.dump_settings('instagram_session.json')
    print("\n✅ Success! Session saved to instagram_session.json")
    print("\nNext step: Run this command to get the session data:")
    print("  cat instagram_session.json | base64")
    print("\nThen add that output as a GitHub secret named INSTAGRAM_SESSION")
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nIf Instagram asks for verification, check your email/SMS and try again.")
