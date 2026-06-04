from flask import Flask, request, jsonify, send_file
import requests
import io
import os
import subprocess
import tempfile
import uuid

app = Flask(__name__)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
PEXELS_API_KEY = os.environ.get('PEXELS_API_KEY')

VOICES = {
    'ru': 'nova',
    'uk': 'shimmer'
}

def generate_tts(text, lang='ru'):
    voice = VOICES.get(lang, 'nova')
    response = requests.post(
        'https://api.openai.com/v1/audio/speech',
        headers={
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'tts-1',
            'input': text,
            'voice': voice,
            'speed': 1.1
        }
    )
    return response.content if response.status_code == 200 else None

def search_pexels_video(query):
    response = requests.get(
        'https://api.pexels.com/videos/search',
        headers={'Authorization': PEXELS_API_KEY},
        params={'query': query, 'per_page': 3, 'orientation': 'portrait'}
    )
    if response.status_code == 200:
        videos = response.json().get('videos', [])
        if videos:
            files = videos[0].get('video_files', [])
            # Берём файл с наименьшим разрешением для скорости
            files_sorted = sorted(files, key=lambda x: x.get('width', 0))
            for f in files_sorted:
                if f.get('width', 0) >= 360:
                    return f.get('link')
    return None

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text = data.get('text', '')
    lang = data.get('lang', 'ru')
    audio = generate_tts(text, lang)
    if not audio:
        return jsonify({'error': 'TTS failed'}), 500
    return send_file(io.BytesIO(audio), mimetype='audio/mpeg',
                     as_attachment=True, download_name=f'voice_{lang}.mp3')

@app.route('/video', methods=['POST'])
def video():
    data = request.json
    script = data.get('script', '')
    films = data.get('films', ['cinema', 'movie', 'film'])
    lang = data.get('lang', 'ru')

    tmpdir = tempfile.mkdtemp()
    job_id = str(uuid.uuid4())[:8]

    # Генерируем голос
    audio_data = generate_tts(script, lang)
    if not audio_data:
        return jsonify({'error': 'TTS failed'}), 500

    audio_path = os.path.join(tmpdir, 'voice.mp3')
    with open(audio_path, 'wb') as f:
        f.write(audio_data)

    # Скачиваем видео с Pexels
    video_paths = []
    queries = [films[0] if films else 'cinema', 'movie theater', 'popcorn cinema']

    for i, query in enumerate(queries[:3]):
        url = search_pexels_video(query)
        if url:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                vpath = os.path.join(tmpdir, f'clip_{i}.mp4')
                with open(vpath, 'wb') as f:
                    f.write(r.content)
                video_paths.append(vpath)

    if not video_paths:
        return jsonify({'error': 'No videos found'}), 500

    # Создаём файл списка для FFmpeg
    list_path = os.path.join(tmpdir, 'list.txt')
    with open(list_path, 'w') as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")

    # Склеиваем клипы
    concat_path = os.path.join(tmpdir, 'concat.mp4')
    subprocess.run([
        'ffmpeg', '-f', 'concat', '-safe', '0',
        '-i', list_path,
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
        '-an', '-y', concat_path
    ], capture_output=True)

    # Накладываем голос
    output_path = os.path.join(tmpdir, f'output_{job_id}.mp4')
    subprocess.run([
        'ffmpeg',
        '-i', concat_path,
        '-i', audio_path,
        '-map', '0:v', '-map', '1:a',
        '-c:v', 'copy', '-c:a', 'aac',
        '-shortest', '-y', output_path
    ], capture_output=True)

    if not os.path.exists(output_path):
        return jsonify({'error': 'Video generation failed'}), 500

    return send_file(output_path, mimetype='video/mp4',
                     as_attachment=True, download_name='video.mp4')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
