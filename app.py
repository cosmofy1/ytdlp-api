from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import json

app = Flask(__name__)
CORS(app)

# Простой кэш в памяти
cache = {}

@app.route('/audio/<video_id>')
def get_audio(video_id):
    # Проверяем кэш
    if video_id in cache:
        return jsonify(cache[video_id])
    
    try:
        # Получаем прямой URL аудио
        result = subprocess.run([
            'yt-dlp',
            '-g',  # Только URL, без скачивания
            '-f', 'bestaudio[ext=m4a]/bestaudio',
            '--no-warnings',
            '--no-playlist',
            f'https://youtube.com/watch?v={video_id}'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            response = {
                'audioUrl': result.stdout.strip(),
                'source': 'yt-dlp',
                'videoId': video_id
            }
            cache[video_id] = response
            return jsonify(response)
        
        return jsonify({'error': 'Failed to get audio URL'}), 500
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/info/<video_id>')
def get_info(video_id):
    try:
        result = subprocess.run([
            'yt-dlp',
            '-j',  # JSON информация
            '--no-warnings',
            '--no-playlist',
            f'https://youtube.com/watch?v={video_id}'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return jsonify({
                'title': info.get('title'),
                'artist': info.get('artist') or info.get('uploader'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail')
            })
        
        return jsonify({'error': 'Failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/')
def home():
    return jsonify({
        'service': 'yt-dlp API',
        'endpoints': ['/audio/<video_id>', '/info/<video_id>', '/health']
    })

from flask import Response
import requests

@app.route('/stream/<video_id>')
def stream(video_id):
    try:
        # Получаем прямой URL аудио
        result = subprocess.run([
            'yt-dlp',
            '-g',
            '-f', 'bestaudio[ext=m4a]/bestaudio',
            '--no-warnings',
            '--no-playlist',
            f'https://youtube.com/watch?v={video_id}'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0 or not result.stdout.strip():
            return jsonify({'error': 'Failed to get audio URL'}), 500

        audio_url = result.stdout.strip()

        # Проксируем поток к пользователю
        def generate():
            with requests.get(audio_url, stream=True) as r:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk

        return Response(generate(),
                        content_type='audio/mpeg',
                        headers={
                            "Accept-Ranges": "bytes",
                            "Access-Control-Allow-Origin": "*"
                        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
