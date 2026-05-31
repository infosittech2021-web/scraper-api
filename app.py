import os
import subprocess
import sys

# Set browser path to local project folder
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '0')

from flask import Flask, request, jsonify
from flask_cors import CORS
from extractors import extract_google_maps
import traceback

app = Flask(__name__)
CORS(app)


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    pw_status = 'unknown'
    try:
        from playwright.sync_api import sync_playwright
        pw_status = 'installed'
    except ImportError:
        pw_status = 'not_installed'

    return jsonify({
        'status': 'ok',
        'service': 'scraper-api',
        'version': '2.3.0',
        'playwright': pw_status,
    })


# പുതിയതായി ചേർത്ത Endpoint: ഇത് ബ്രൗസർ ഇൻസ്റ്റാൾ ചെയ്യാൻ സഹായിക്കും
@app.route('/install-browser', methods=['GET'])
def install_browser():
    try:
        # Run playwright install and capture output
        result1 = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, text=True)
        result2 = subprocess.run([sys.executable, "-m", "playwright", "install-deps", "chromium"], capture_output=True, text=True)
        
        return jsonify({
            'status': 'success',
            'message': 'Installation attempted',
            'install_output': result1.stdout + "\n" + result1.stderr,
            'deps_output': result2.stdout + "\n" + result2.stderr
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })


@app.route('/extract', methods=['POST'])
def extract():
    data = request.json
    source = data.get('source')
    category = data.get('category')
    location = data.get('location')
    page = data.get('page', 1)

    if not category or not location:
        return jsonify({'status': 'error', 'message': 'Category and location are required'}), 400

    try:
        if source == 'google_maps':
            result = extract_google_maps(category, location, int(page))
        else:
            return jsonify({'status': 'error', 'message': f'Source "{source}" not implemented.'}), 400

        if result['total'] == 0 and result.get('debug'):
            return jsonify({
                'status': 'error',
                'message': f"Render Error: {result['debug'][0]}"
            })

        return jsonify({'status': 'success', **result, 'source': source})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(port=5000, debug=True)
