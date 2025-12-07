import time
import subprocess
import requests
from flask import Flask, jsonify, Response

app = Flask(__name__)

# ===== КЕШ =====
cache = {}
CACHE_TTL = 18000  # 5 часов (YouTube ссылки живут около 5-6 часов)

def get_cached(video_id):
    """Возвращает кешированный URL, если не истёк"""
    if video_id in cache:
        entry = cache[video_id]
        if entry['expires'] > time.time():
            print(f"[CACHE HIT] {video_id}")
            return entry['url']
        else:
            del cache[video_id]
    return None

def set_cache(video_id, url):
    """Сохраняет URL в кеш"""
    cache[video_id] = {
        'url': url,
        'expires': time.time() + CACHE_TTL
    }
    print(f"[CACHE SET] {video_id}")

# ===== API =====

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/audio/<video_id>")
def get_audio(video_id):
    cached = get_cached(video_id)
    if cached:
        return jsonify({"audioUrl": cached, "source": "cache", "videoId": video_id})

    result = subprocess.run([
        "yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio",
        "-g", f"https://youtube.com/watch?v={video_id}"
    ], capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout.strip():
        return jsonify({"error": "Failed to get audio URL"}), 500

    url = result.stdout.strip()
    set_cache(video_id, url)
    return jsonify({"audioUrl": url, "source": "yt-dlp", "videoId": video_id})

@app.route("/stream/<video_id>")
def stream(video_id):
    # 1. Проверяем кеш
    cached = get_cached(video_id)
    if cached:
        print(f"[STREAM FROM CACHE] {video_id}")
        audio_url = cached
    else:
        print(f"[STREAM NEW] {video_id}")
        result = subprocess.run([
            "yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio",
            "-g", f"https://youtube.com/watch?v={video_id}"
        ], capture_output=True, text=True)

        if result.returncode != 0 or not result.stdout.strip():
            return jsonify({"error": "Failed to get audio URL"}), 500

        audio_url = result.stdout.strip()
        set_cache(video_id, audio_url)

    # 2. Проксируем поток
    def generate():
        with requests.get(audio_url, stream=True) as r:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

    return Response(generate(),
                    content_type="audio/mpeg",
                    headers={"Access-Control-Allow-Origin": "*",
                             "Accept-Ranges": "bytes"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
