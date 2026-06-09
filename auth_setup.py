"""
auth_setup.py
Run once to generate a YouTube refresh token.
Requires: client_secret.json in the same folder.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

def main():
    flow = InstalledAppFlow.from_client_secrets_file(
        "client_secret.json",
        SCOPES
    )

    creds = flow.run_local_server(
        host="localhost",
        port=8080,
        open_browser=False
    )

    print("\n" + "=" * 60)
    print("✅ Authentication successful!")
    print("\nAdd this line to your .env file:\n")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()