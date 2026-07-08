from trading_app.schwab_keepass_extractor import SchwabKeyExtractor
from schwab.auth import easy_client

#
# Add code to pull CLIENT data from KEEPASS database.
#

SCHWAB_AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

CLIENT_ID = ""
CLIENT_SECRET = ""

APP_IP = "127.0.0.1"
APP_PORT = 55665
CALLBACK_URL = f"https://{APP_IP}:{APP_PORT}"
TOKEN_PATH = "./tokens/token.json"

def clear_local_creds():
    global CLIENT_ID, CLIENT_SECRET
    CLIENT_ID = ""
    CLIENT_SECRET = ""

def load_credentials_from_keepass(config_path: str):
    extractor = SchwabKeyExtractor(config_path)
    extractor.open_database()

    client_id = extractor.extract_field("client_id")
    client_secret = extractor.extract_field("client_secret")

    return client_id, client_secret

def get_easy_client(config_path: str):

    global CLIENT_ID, CLIENT_SECRET

    CLIENT_ID, CLIENT_SECRET = load_credentials_from_keepass(config_path)
 
    # Follow the instructions on the screen to authenticate your client.
    c = easy_client(
        api_key=CLIENT_ID,
        app_secret=CLIENT_SECRET,
        callback_url=CALLBACK_URL,
        token_path=TOKEN_PATH,
        interactive=False,
        asyncio=True)
    
    return c