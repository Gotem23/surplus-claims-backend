import os
from urllib.parse import urlparse

env = os.getenv("ENV", "").strip()
dburl = os.getenv("DATABASE_URL", "").strip()
cors = os.getenv("CORS_ORIGINS", "").strip()
raw = os.getenv("API_KEY_HASHES", "").strip()

p = urlparse(dburl)

db_name = (p.path or "").lstrip("/")
db_user = p.username or ""
db_host = p.hostname or ""

hashes = []
for h in raw.split(","):
    h = h.strip().strip('"').strip("'")
    if h:
        hashes.append(h)

print("ENV =", env)
print("DB_NAME =", db_name)
print("DB_USER =", db_user)
print("DB_HOST =", db_host)
print("CORS_SET =", bool(cors))
print("API_KEY_HASHES_COUNT =", len(hashes))
