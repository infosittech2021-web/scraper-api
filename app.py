from flask import Flask, request, jsonify
from flask_cors import CORS
from extractors import extract_google_maps

app = Flask(__name__)
CORS(app)

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
        page_num = int(page)
        
        if source == 'google_maps':
            result = extract_google_maps(category, location, page_num)
        else:
            return jsonify({'status': 'error', 'message': f'Source {source} not implemented yet in Python scraper.'}), 400
            
        return jsonify({
            'status': 'success',
            **result,
            'source': source
        })
        
    except Exception as e:
        print(f"Extraction error for {source}:", e)
        return jsonify({'status': 'error', 'message': str(e) or 'Failed to extract leads'}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
