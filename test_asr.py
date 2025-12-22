import os
from dotenv import load_dotenv

load_dotenv()

secret = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
print("Secret length:", len(secret))
print("Secret repr:", repr(secret))
print("Ends with:", secret[-5:])