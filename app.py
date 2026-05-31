import os
import subprocess

# Must be set before importing Playwright
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '0')

# Force install Chromium every time the app starts on Render
# This guarantees the browser binary is always available, even on the free tier
print("Checking/Installing Playwright Chromium...")
subprocess.run(["playwright", "install", "chromium"], check=False)
subprocess.run(["playwright", "install-deps", "chromium"], check=False)
print("Playwright check complete.")

from flask import Flask, request, jsonify
from flask_cors import CORS
from extractors import extract_google_maps
import traceback

app = Flask(__name__)
CORS(app)


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    """Health-check endpoint for monitoring."""
    pw_status = 'unknown'
    try:
        from playwright.sync_api import sync_playwright
        pw_status = 'installed'
    except ImportError:
        pw_status = 'not_installed'

    return jsonify({
        'status': 'ok',
        'service': 'scraper-api',
        'version': '2.2.0',
        'playwright': pw_status,
    })


@app.route('/extract', methods=['POST'])
def extract():
    data = request.json
    source = data.get('source')
    category = data.get('category')
    location = data.get('location')
    page = data.get('page', 1)

    if not category or not location:
        return jsonify({
            'status': 'error',
            'message': 'Category and location are required',
        }), 400

    try:
        page_num = int(page)

        if source == 'google_maps':
            result = extract_google_maps(category, location, page_num)
        else:
            return jsonify({
                'status': 'error',
                'message': f'Source "{source}" not implemented yet.',
            }), 400

        # If 0 leads and Playwright failed, show the error alert
        if result['total'] == 0 and result.get('debug'):
            return jsonify({
                'status': 'error',
                'message': f"Render Scraper Error: {result['debug'][0]}"
            })

        return jsonify({
            'status': 'success',
            **result,
            'source': source,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e) or 'Failed to extract leads',
        }), 500


if __name__ == '__main__':
    app.run(port=5000, debug=True)
