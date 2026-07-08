import json
import os
from getpass import getpass
from typing import Optional
from pykeepass import PyKeePass

class SchwabKeyExtractor:
    """
    Extracts Schwab API credentials from a KeePass (.kdbx) database
    using configuration provided in a local JSON file.
    """

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()

        self.kdbx_path = self.config.get("kdbx_path")
        self.entry_title = self.config.get("entry_title", "Schwab API")
        self.field_name = self.config.get("field_name", "api_key")
        self.password_env_var = self.config.get("password_env_var")

        self.kp = None

    def _load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_master_password(self) -> str:
        """
        Retrieves KeePass master password from environment variable
        or prompts user securely.
        """
        if self.password_env_var:
            pwd = os.getenv(self.password_env_var)
            if pwd:
                return pwd

        return getpass("Enter KeePass master password: ")

    def open_database(self) -> None:
        """
        Opens the KeePass database.
        """
        if not self.kdbx_path:
            raise ValueError("Missing 'kdbx_path' in config")

        password = self._get_master_password()

        self.kp = PyKeePass(self.kdbx_path, password=password)

    def find_entry(self):
        """
        Finds the KeePass entry by title.
        """
        if not self.kp:
            raise RuntimeError("Database not opened. Call open_database() first.")

        entry = self.kp.find_entries(title=self.entry_title, first=True)

        if not entry:
            raise KeyError(f"No KeePass entry found with title: {self.entry_title}")

        return entry

    def extract_field(self, field_name: Optional[str] = None) -> str:
        """
        Extracts a field (e.g., API key, client id, secret) from the entry.
        """
        entry = self.find_entry()
        field = field_name or self.field_name

        # Standard KeePass fields
        if hasattr(entry, field):
            value = getattr(entry, field)
            if value:
                return value

        # Fallback: custom properties
        if field in entry.custom_properties:
            return entry.custom_properties[field]

        raise KeyError(f"Field '{field}' not found in entry '{self.entry_title}'")

    def close(self):
        """
        Clears in-memory reference to the database.
        """
        self.kp = None


if __name__ == "__main__":
    """
    Example usage:
    """

    CONFIG_PATH = "./config.json"

    extractor = SchwabKeyExtractor(CONFIG_PATH)

    try:
        extractor.open_database()

        api_key = extractor.extract_field("api_key")
        client_id = extractor.extract_field("client_id")
        client_secret = extractor.extract_field("client_secret")

        print("Schwab API Credentials Loaded:")
        print(f"API Key: {api_key}")
        print(f"Client ID: {client_id}")
        print(f"Client Secret: {client_secret}")

    finally:
        extractor.close()