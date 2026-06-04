from flask import Flask, request, jsonify, send_file
import requests
import io
import os
import subprocess
import tempfile
import uuid
import json
import sys
os.environ['PYTHONUNBUFFERED'] = '1'

app = Flask(__name__)

import traceback

@app.errorhandler(Exception)
def handle_exception(e):
    print("UNHANDLED EXCEPTION:")
    print(traceback.format_exc())
    return jsonify({'error': str(e)}), 500

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

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

def download_poster(poster_path, tmpdir, index):
    url = f"https://image.tmdb.org/t/p/w500{poster_path}"
    r = requests.get(url, timeout=15)
    if r.status_code == 200:
        img_path = os.path.join(tmpdir, f'poster_{index}.jpg')
        with open(img_path, 'wb') as f:
            f.write(r.content)
        print(f"Poster {index} downloaded: {len(r.content)} bytes")
        return img_path
    return None

def make_srt(script, audio_path, tmpdir):
    result = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', audio_path
    ], capture_output=True, text=True)

    duration = 30.0
    try:
        info = json.loads(result.stdout)
        duration = float(info['format']['duration'])
    except:
        pass

    words = script.split()
    chunks = []
    chunk_size = 7
    for i in range(0, len(words), chunk_size):
        chunks.append(' '.join(words[i:i + chunk_size]))

    srt_path = os.path.join(tmpdir, 'subs.srt')
    time_per_chunk = duration / max(len(chunks), 1)

    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, chunk in enumerate(chunks):
            start = i * time_per_chunk
            end = (i + 1) * time_per_chunk
            f.write(f"{i + 1}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{chunk}\n\n")

    return srt_path, duration

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

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
    posters = data.get('posters', [])
    lang = data.get('lang', 'ru')

    print(f"Video request: lang={lang}, posters={posters}")

    tmpdir = tempfile.mkdtemp()
    job_id = str(uuid.uuid4())[:8]

    # Генерируем голос
    audio_data = generate_tts(script, lang)
    if not audio_data:
        return jsonify({'error': 'TTS failed'}), 500

    audio_path = os.path.join(tmpdir, 'voice.mp3')
    with open(audio_path, 'wb') as f:
        f.write(audio_data)

    # Генерируем субтитры
    srt_path, duration = make_srt(script, audio_path, tmpdir)
    time_per_poster = duration / max(len(posters), 1)

    # Скачиваем постеры
    poster_paths = []
    for i, poster in enumerate(posters[:3]):
        path = download_poster(poster, tmpdir, i)
        if path:
            poster_paths.append(path)

    if not poster_paths:
        return jsonify({'error': 'No posters downloaded'}), 500

    # Конвертируем постеры в видеоклипы
    clip_paths = []
    for i, poster_path in enumerate(poster_paths):
        clip_path = os.path.join(tmpdir, f'clip_{i}.mp4')
        subprocess.run([
            'ffmpeg',
            '-loop', '1', '-i', poster_path,
            '-vf', 'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
            '-t', str(time_per_poster),
            '-pix_fmt', 'yuv420p',
            '-an', '-y', clip_path
        ], capture_output=True, text=True)
        if os.path.exists(clip_path):
            clip_paths.append(clip_path)

    if not clip_paths:
        return jsonify({'error': 'Clip generation failed'}), 500

    # Список клипов для FFmpeg
    list_path = os.path.join(tmpdir, 'list.txt')
    with open(list_path, 'w') as f:
        for cp in clip_paths:
            f.write(f"file '{cp}'\n")

    # Склеиваем клипы
    concat_path = os.path.join(tmpdir, 'concat.mp4')
    result1 = subprocess.run([
        'ffmpeg', '-f', 'concat', '-safe', '0',
        '-i', list_path,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
        '-an', '-y', concat_path
    ], capture_output=True, text=True)
    print("CONCAT:", result1.stderr[-200:])

    # Накладываем голос + субтитры
    output_path = os.path.join(tmpdir, f'output_{job_id}.mp4')
    result2 = subprocess.run([
        'ffmpeg',
        '-i', concat_path,
        '-i', audio_path,
        '-map', '0:v', '-map', '1:a',
        '-vf', f"subtitles='{srt_path}':force_style='FontName=Arial,FontSize=14,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2,MarginV=40'",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
        '-c:a', 'aac', '-shortest', '-y', output_path
    ], capture_output=True, text=True)
    print("OUTPUT:", result2.stderr[-200:])

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        return jsonify({'error': 'Video generation failed'}), 500

    print(f"Done: {os.path.getsize(output_path)} bytes")
    return send_file(output_path, mimetype='video/mp4',
                     as_attachment=True, download_name='video.mp4')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
