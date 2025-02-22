from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import logging
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Set up Gemini API key
genai.configure(api_key="AIzaSyDJg_6FdCqAGScGWQ3lQsW1rbVOJkGOeoU")

# Ensure the directory exists for storing PDFs
PDF_DIR = "static/pitches"
os.makedirs(PDF_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-pitch', methods=['POST'])
def generate_pitch():
    try:
        app.logger.info("Received request to generate pitch")
        data = request.json
        app.logger.debug(f"Received data: {data}")

        # Validate required fields
        required_fields = ['businessName', 'industry', 'problemStatement', 'targetMarket', 'revenueModel']
        for field in required_fields:
            if field not in data or not data[field]:
                app.logger.error(f"Missing required field: {field}")
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Prepare the prompt for Gemini
        prompt = f"""
        Create a professional business pitch for:

        Business Name: {data['businessName']}
        Industry: {data['industry']}
        Problem Statement: {data['problemStatement']}
        Target Market: {data['targetMarket']}
        Revenue Model: {data['revenueModel']}
        {"Competitor Analysis: " + data['competitorAnalysis'] if 'competitorAnalysis' in data and data['competitorAnalysis'] else ""}

        Format the pitch with these sections:

        🎯 Problem Statement
        💡 Solution Overview
        📊 Market Opportunity
        💰 Revenue Model
        🏆 Competitive Advantage
        ⚡ Call to Action

        Make it concise, compelling, and ready for presentation.
        """

        # Use Gemini API to generate text
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)

        if not response or not response.text:
            app.logger.error("No pitch was generated")
            return jsonify({"error": "No pitch was generated"}), 500

        generated_pitch = response.text
        app.logger.info("Successfully generated pitch")

        # Generate PDF
        pdf_filename = f"{data['businessName'].replace(' ', '_')}_pitch.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)

        create_pdf(generated_pitch, pdf_path)

        return jsonify({
            "pitch": generated_pitch,
            "pdf_download_url": f"/download-pdf/{pdf_filename}"
        })

    except Exception as e:
        app.logger.error(f"Error: {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

def create_pdf(text, filepath):
    """Helper function to create a PDF from text."""
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    # Set font
    c.setFont("Helvetica", 12)

    # Set starting position
    y_position = height - 40

    for line in text.split("\n"):
        c.drawString(50, y_position, line)
        y_position -= 20  # Move down

        if y_position < 40:  # Prevent text from running off the page
            c.showPage()
            c.setFont("Helvetica", 12)
            y_position = height - 40

    c.save()

@app.route('/download-pdf/<filename>')
def download_pdf(filename):
    """Endpoint to download the generated PDF."""
    pdf_path = os.path.join(PDF_DIR, filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
