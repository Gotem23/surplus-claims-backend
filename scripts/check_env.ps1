# check_env.ps1
# Prints key env/safety info (no secrets)

python -c "import os; from urllib.parse import urlparse; env=(os.getenv('ENV') or os.getenv('APP_ENV') or '').strip(); db=os.getenv('DATABASE_URL','').strip(); cors=os.getenv('CORS_ORIGINS','').strip(); raw=os.getenv('API_KEY_HASHES','').strip(); p=urlparse(db); db_name=(p.path or '').lstrip('/'); db_user=p.username or ''; db_host=p.hostname or ''; hs=[h.strip() for h in raw.split(',') if h.strip()]; print('ENV =',env); print('DB_NAME =',db_name); print('DB_USER =',db_user); print('DB_HOST =',db_host); print('CORS_SET =',bool(cors)); print('API_KEY_HASHES_COUNT =',len(hs))"
