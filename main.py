from flask import Flask, request, jsonify, send_file
import requests
import io
import os

app = Flask(__name__)

ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
VOICE_ID = 'pNInz6obpgDQGcFmaJgB'

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text = data.get('text', '')
    
    print(f"API KEY: {ELEVENLABS_API_KEY[:10] if ELEVENLABS_API_KEY else 'NOT SET'}")
    print(f"Text: {text[:50]}")
    
    response = requests.post(
        f'https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}',
        headers={
            'xi-api-key': ELEVENLABS_API_KEY,
            'Content-Type': 'application/json'
        },
        json={
            'text': text,
            'model_id': 'eleven_multilingual_v2',
            'voice_settings': {
                'stability': 0.5,
                'similarity_boost': 0.75
            }
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    if response.status_code != 200:
        return jsonify({'error': response.text}), 500
    
    audio_buffer = io.BytesIO(response.content)
    audio_buffer.seek(0)
    return send_file(audio_buffer, mimetype='audio/mpeg',
                     as_attachment=True, download_name='voice.mp3')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
