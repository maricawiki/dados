"""Download bounded official ISP files, retrying only transient transport errors."""
import time
import urllib.error
import urllib.request

def download(url, limit, timeout=90, attempts=3):
    req = urllib.request.Request(url, headers={"User-Agent": "MaricaWiki-Observatorio/1.0", "Accept": "text/csv,*/*"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read(limit + 1)
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt + 1 == attempts:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt + 1 == attempts:
                raise
        print(f"::warning::Falha transitória ISP; nova tentativa {attempt+2}/{attempts}")
        time.sleep(2 ** (attempt + 1))
