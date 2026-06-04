from flask import Flask, request, jsonify, send_file
import requests
import io
import os

app = Flask(__name__)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

VOICES = {
    'ru': 'nova',
    'uk': 'shimmer'
}

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text = data.get('text', '')
    lang = data.get('lang', 'ru')
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

    if response.status_code != 200:
        return jsonify({'error': response.text}), 500

    audio_buffer = io.BytesIO(response.content)
    audio_buffer.seek(0)
    return send_file(audio_buffer, mimetype='audio/mpeg',
                     as_attachment=True, download_name=f'voice_{lang}.mp3')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
