import time
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import yt_dlp

app = FastAPI()

# ========== КЕШИРОВАНИЕ ==========
audio_url_cache = {}
CACHE_TTL = 18000  # 5 часов в секундах

def get_cached_url(video_id: str) -> str | None:
    """Получить URL из кеша, если не истёк"""
    if video_id in audio_url_cache:
        entry = audio_url_cache[video_id]
        if entry['expires'] > time.time():
            print(f"✅ [CACHE HIT] {video_id}")
            return entry['url']
        else:
            print(f"⏰ [CACHE EXPIRED] {video_id}")
            del audio_url_cache[video_id]
    return None

def set_cached_url(video_id: str, url: str):
    """Сохранить URL в кеш"""
    audio_url_cache[video_id] = {
        'url': url,
        'expires': time.time() + CACHE_TTL
    }
    print(f"💾 [CACHE SET] {video_id} -> expires in 5h")

# ========== YT-DLP ==========
def extract_audio_url(video_id: str) -> str:
    """Получить direct audio URL через yt-dlp"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", 
            download=False
        )
        return info['url']

# ========== ENDPOINTS ==========
@app.get("/audio/{video_id}")
async def get_audio_url(video_id: str):
    """Возвращает direct audio URL (с кешированием)"""
    
    # 1. Проверить кеш
    cached = get_cached_url(video_id)
    if cached:
        return {"audioUrl": cached, "source": "cache", "cached": True}
    
    # 2. Если нет в кеше — yt-dlp
    print(f"🔍 [YT-DLP] Extracting {video_id}...")
    start = time.time()
    
    url = extract_audio_url(video_id)
    
    elapsed = time.time() - start
    print(f"✅ [YT-DLP] Done in {elapsed:.1f}s")
    
    # 3. Сохранить в кеш
    set_cached_url(video_id, url)
    
    return {"audioUrl": url, "source": "yt-dlp", "cached": False}


@app.get("/stream/{video_id}")
async def stream_audio(video_id: str):
    """Стриминг аудио (с кешированием URL)"""
    
    # 1. Проверить кеш — если есть, стримим СРАЗУ
    cached = get_cached_url(video_id)
    if cached:
        print(f"🚀 [STREAM] Fast start from cache: {video_id}")
        return await stream_from_url(cached)
    
    # 2. Если нет в кеше — получить и закешировать
    print(f"⏳ [STREAM] Cache miss, extracting: {video_id}")
    url = extract_audio_url(video_id)
    set_cached_url(video_id, url)
    
    return await stream_from_url(url)


async def stream_from_url(url: str):
    """Стриминг из direct URL"""
    import httpx
    
    async def generate():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url) as response:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk
    
    return StreamingResponse(
        generate(),
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        }
    )
