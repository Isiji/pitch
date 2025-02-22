from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import json
import logging
import time
import requests
from huggingface_hub import InferenceClient
from pathlib import Path
from io import BytesIO
import base64
from PIL import Image
from utils import gen_cases, get_response_gemini, generate_product_guidance  # keep these for other endpoints

from dotenv import load_dotenv
load_dotenv()


from flask import Flask, render_template, url_for, send_from_directory, request, jsonify, session, redirect, url_for, session
from utils import gen_cases,  get_response_gemini  # added the import for get_response_gemini function
import sqlalchemy
from pathlib import Path
import json
import os
import logging
import time
from huggingface_hub import InferenceClient
from io import BytesIO
import base64
from PIL import Image

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True  # For development: auto-reload templates
# Use a fixed secret key (or load from environment) for sessions
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")
app.jinja_env.globals.update(str=str, time=time)

BASE_DIR = Path(__file__).resolve().parent

# File paths
USER_DATA_FILE = BASE_DIR / "data/users.json"
# NOTE: Removed SCENARIOS_FILE since scenarios will now be generated dynamically.

# ----------------------------
# Helper functions for JSON I/O
# ----------------------------
def read_json(file_path):
    if not os.path.exists(file_path):
        with open(file_path, 'w') as file:
            json.dump([], file)
    with open(file_path, 'r') as file:
        return json.load(file)

def write_json(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)
    print(f"Updated JSON file: {file_path}")


logger = logging.getLogger('my_app')
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler('flask_app.log')
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.debug("Logger configured. Starting app...")

# ----------------------------
# Routes
# ----------------------------


@app.route('/')
def index():
    return render_template('index.html')













@app.route('/generate_product_guidance', methods=['POST'])
def generate_product_guidance_endpoint():
    data = request.get_json()
    problem_statement = data.get('problem_statement')
    industry = data.get('industry')
    technology = data.get('technology')
    target_audience = data.get('target_audience')

    if not all([problem_statement, industry, technology, target_audience]):
        return jsonify({"error": "problem_statement, industry, technology, and target_audience are required."}), 400

    try:
        guidance = generate_product_guidance(problem_statement, industry, technology, target_audience)
        return jsonify(guidance), 200
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500


if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    read_json(USER_DATA_FILE)
    app.run(debug=True)
