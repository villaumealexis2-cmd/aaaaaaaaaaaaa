import os
import sys
import json
import base64
import requests
import hashlib
import time
import io
from PIL import Image

# Customer settings
IMAGE_PATH = 'mymotd.png'  # Works best with 64x16 or 64x64
OUT_DIR = 'BannerMOTD'
OUT_JSON = os.path.join(OUT_DIR, 'motd.json')
CACHE_FILE = 'skin_cache.json'

def get_block_hash(img):
    return hashlib.md5(img.tobytes()).hexdigest()

def strip_metadata(base64_texture):
    """Strips unnecessary MineSkin metadata to prevent Minecraft packets from being too large."""
    try:
        decoded = base64.b64decode(base64_texture).decode('utf-8')
        data = json.loads(decoded)
        
        # Only keep the absolute minimum required by Minecraft
        minified = {
            "textures": {
                "SKIN": {
                    "url": data['textures']['SKIN']['url']
                }
            }
        }
        return base64.b64encode(json.dumps(minified, separators=(',', ':')).encode('utf-8')).decode('utf-8')
    except Exception as e:
        return base64_texture

def main():
    target_img = sys.argv[1] if len(sys.argv) > 1 else IMAGE_PATH
    
    if not os.path.exists(target_img):
        print(f"[!] Error: Target image '{target_img}' not found.")
        print(f"[!] Please place an image named '{target_img}' in this folder.")
        sys.exit(1)

    print(f"[*] Processing image: {target_img}")
    full_img = Image.open(target_img).convert('RGBA')
    width, height = full_img.size

    if height != 16:
        print("[!] Warning: Image height is not 16. The MOTD trick natively uses exactly 2 lines of 8px. It might look cut off.")

    cols = width // 8
    rows = height // 8
    print(f"[*] Splitting image into {cols}x{rows} grid (Total {cols*rows} characters)")

    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)

    extra_components = []
    total = rows * cols
    current = 0

    for r in range(rows):
        for c in range(cols):
            current += 1
            left = c * 8
            upper = r * 8
            block = full_img.crop((left, upper, left + 8, upper + 8))
            
            # Process transparent blocks as blank heads to maintain perfect alignment
            alpha_extrema = block.getextrema()[-1]
            if alpha_extrema == (0, 0):
                pass

            b_hash = get_block_hash(block)
            if b_hash in cache:
                print(f"[{current}/{total}] Loaded chunk from cache...")
                val = cache[b_hash]
            else:
                skin = Image.new('RGBA', (64, 64), (0,0,0,0))
                skin.paste(block, (8, 8))
                buf = io.BytesIO()
                skin.save(buf, format='PNG')
                buf.seek(0)

                print(f"[{current}/{total}] Uploading chunk to MineSkin... (Waiting 6s)")
                while True:
                    try:
                        resp = requests.post(
                            'https://api.mineskin.org/generate/upload',
                            headers={'User-Agent': 'Premium-Banner-MOTD'},
                            files={'file': ('skin.png', buf.getvalue(), 'image/png')}
                        )
                        if resp.status_code == 200:
                            raw_val = resp.json()['data']['texture']['value']
                            val = strip_metadata(raw_val) # Minify it!
                            cache[b_hash] = val
                            with open(CACHE_FILE, 'w') as f:
                                json.dump(cache, f)
                            print(" => Upload Success!")
                            time.sleep(6.2) # Required delay to prevent 429 spam
                            break
                        elif resp.status_code == 429:
                            print(" => Rate limited! Waiting 10s...")
                            time.sleep(10)
                        else:
                            print(" => Error! Retrying in 10s...")
                            time.sleep(10)
                    except Exception as e:
                        time.sleep(10)

            extra_components.append({
                "hat": True,
                "player": {
                    "name": "",
                    "properties": [{"name": "textures", "value": val}]
                }
            })

        if r < rows - 1:
            extra_components.append({"text": ".", "color": "black", "shadow_color": 0, "extra": ["\n"]})
        else:
            extra_components.append({"text": ".", "color": "black", "shadow_color": 0})

    motd_json = {
        "text": "",
        "color": "white",
        "shadow_color": -1,
        "extra": extra_components
    }

    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)

    with open(OUT_JSON, 'w') as f:
        json.dump(motd_json, f, separators=(',', ':'))

    print(f"\n[+] Success! Your {OUT_JSON} has been generated.")
    print(f"[+] To install: Move the entire '{OUT_DIR}' folder and the BannerMOTD.jar into your server's 'plugins/' folder!")

if __name__ == '__main__':
    main()