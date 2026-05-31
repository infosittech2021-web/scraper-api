import os
import sys
import subprocess
import threading
import traceback

# Must be set before importing Playwright
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '0')

from flask import Flask, request, jsonify
from flask_cors import CORS
from extractors import extract_google_maps

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
        'version': '2.5.0',
        'playwright': pw_status,
    })


@app.route('/install-browser', methods=['GET'])
def install_browser():
    """
    Manually trigger browser installation IN THE BACKGROUND
    so it doesn't timeout the 30-second Render limit.
    """
    def run_install():
        try:
            print("Starting background installation of Playwright...")
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
            subprocess.run([sys.executable, "-m", "playwright", "install-deps", "chromium"], check=False)
            print("Background installation finished.")
        except Exception as e:
            print(f"Background install error: {e}")

    # Start the installation in a background thread
    thread = threading.Thread(target=run_install)
    thread.start()

    return jsonify({
        'status': 'success',
        'message': 'Installation started in the background! Please wait 2-3 minutes before extracting leads in the admin panel.'
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
        return jsonify({'status': 'error', 'message': str(e) or 'Failed to extract leads'}), 500


if __name__ == '__main__':
    app.run(port=5000, debug=True)
