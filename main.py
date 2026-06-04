from flask import Flask, request, jsonify, send_file
import requests
import io
import os

app = Flask(__name__)

ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')

VOICES = {
    'ru': 'm0OQuJtWCw1V23P0pQmG',
    'uk': 'l0FRhtyn0AKRYadUAdgv'
}

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text = data.get('text', '')
    lang = data.get('lang', 'ru')
    voice_id = VOICES.get(lang, VOICES['ru'])

    response = requests.post(
        f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
        headers={
            'xi-api-key': ELEVENLABS_API_KEY,
            'Content-Type': 'application/json'
        },
        json={
            'text': text,
            'model_id': 'eleven_multilingual_v2',
            'voice_settings': {
                'stability': 0.4,
                'similarity_boost': 0.75,
                'style': 0.5,
                'use_speaker_boost': True
            }
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
