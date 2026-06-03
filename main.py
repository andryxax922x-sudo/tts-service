from flask import Flask, request, jsonify, send_file
import edge_tts
import asyncio
import io
import os

app = Flask(__name__)

@app.route('/tts', methods=['POST'])
async def tts():
    data = request.json
    text = data.get('text', '')
    voice = data.get('voice', 'ru-RU-SvetlanaNeural')
    
    communicate = edge_tts.Communicate(text, voice)
    audio_buffer = io.BytesIO()
    
    async for chunk in communicate.stream():
        if chunk['type'] == 'audio':
            audio_buffer.write(chunk['data'])
    
    audio_buffer.seek(0)
    return send_file(audio_buffer, mimetype='audio/mpeg', 
                     as_attachment=True, download_name='voice.mp3')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
