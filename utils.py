# your_flask_app/utils.py
import sqlalchemy
import logging
import json
from pathlib import Path
from datetime import datetime
import requests
from io import BytesIO
from PIL import Image
import ast
import google.generativeai as genai  # Import Gemini module
from dotenv import load_dotenv  # Import dotenv for loading .env file
import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
# Load environment variables

import uuid  # Import uuid for unique ID generation





Base = declarative_base() #SQLAlchemy Base



load_dotenv()

# Load the API key from environment variables
GENAI_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GENAI_API_KEY:
    raise ValueError("GOOGLE_API_KEY is not set in the .env file.")
genai.configure(api_key=GENAI_API_KEY)

# Define the base directory for the Flask app
BASE_DIR = Path(__file__).resolve().parent

# Load prompts from JSON file
PROMPTS_FILE = BASE_DIR / "prompts.json"
if not PROMPTS_FILE.exists():
    raise FileNotFoundError(f"Prompts file not found at {PROMPTS_FILE}")

with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
    prompts = json.load(f)

timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
logger = logging.getLogger('my_app')
logger.setLevel(logging.DEBUG)

# Directory to save generated cases and images
output_path = BASE_DIR / 'output/game'
output_path.mkdir(parents=True, exist_ok=True)

# Function to get a response from Gemini
def get_response_gemini(prompt: str) -> str:
    try:
        logger.debug(f"Generating response for prompt: {prompt[:50]}...")
        model = genai.GenerativeModel('gemini-2.0-flash-exp')  # Update the model name
        response = model.generate_content(prompt)

        if response and response._result.candidates:
            content = response._result.candidates[0].content.parts[0].text.strip()
            logger.debug(f"Received response: {content[:5000]}...")
            return content
        else:
            logger.error("Empty or invalid response from Gemini.")
            return ""
    except Exception as err:
        logger.error(f"Error generating response: {err}")
        return ""

# Function to clean the response from code block formatting
def clean_response(response: str) -> str:
    if response.startswith("```python") and response.endswith("```"):
        return response[len("```python"): -len("```")].strip()
    return response

# Function to extract the list from the cleaned response
def extract_list(code: str) -> str:
    try:
        code = code.replace("\'", "\\'")  # Replacing every \' with \\'
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.Expr)):  # Handle both named and unnamed lists
                if isinstance(node.value, ast.List):
                    extracted_list = ast.literal_eval(node.value)  # safely convert the list
                    return json.dumps(extracted_list)  # Convert to JSON
        return None
    except (SyntaxError, ValueError, TypeError) as e:
        logger(f"Error parsing or evaluating Python code: {e}")
        logger(f"Problematic code snippet: {code}")
        return None


def gen_cases(language: str, difficulty: str, age: int, output_dir: Path, subject: str, question_type: str, subtype: str, conversation_data=None, sex: str = 'unspecified'):
    logger = logging.getLogger('my_app')
    logger.debug(f"gen_cases function called with parameters: language={language}, age={age}, subject={subject}, difficulty={difficulty}, question_type={question_type}, subtype={subtype}, sex={sex}, conversation_data={conversation_data}")

    try:
        if conversation_data is None:
            if question_type == 'behavioral':
                prompt = f"""{prompts['cases']} Respond in {language}. The content should be appropriate for a person aged {age} and the subject/theme used should be {subject}. Set the difficulty of the content to {difficulty}. The person is {sex}. The subtype is {subtype}."""
            elif question_type == 'study':
                prompt = f"""{prompts['study']} Respond in {language}. The content should be appropriate for a person aged {age} and the subject/theme used should be {subject}. Set the difficulty of the content to {difficulty}. The person is {sex}. The subtype is {subtype}."""
            elif question_type == 'hiring':
                prompt = f"""{prompts['hiring']} Respond in {language}. The content should be appropriate for a person aged {age} and the subject/theme used should be {subject}. Set the difficulty of the content to {difficulty}. The person is {sex}. The subtype is {subtype}."""
            logger.debug(f"Initial prompt generated: {prompt}")
        else:
            # conversation_data now has the structure: { "data": { "cases": [ ... ] } }
            previous_cases = conversation_data.get('data', {}).get('cases', [])
            if not isinstance(previous_cases, list) or not previous_cases:
                logger.warning("No previous cases found in conversation data. Returning None.")
                return None, conversation_data

            # Construct a clear textual representation of all previous cases
            previous_turn_summary = ""
            for case in previous_cases:
                user_choice = case.get('user_answer')
                previous_case = case.get('case', "Unknown Case")
                previous_options = case.get('options', [])
                previous_turn_summary += f"Previous Case: {previous_case}\nThe person was presented with the following options:\n"
                for option in previous_options:
                    previous_turn_summary += f"- Option {option['number']}: {option['option']}\n"
                previous_turn_summary += f"\nThe person selected option {user_choice}.\n\n"

            if question_type == 'behavioral':
                prompt = f"""{prompts['cases']} The person's previous responses were as follows:\n{previous_turn_summary}For the case, ask another question with the SAME STRUCTURE based on their previous responses in {language} appropriate for the age {age} with the theme '{subject}'. Set the difficulty of the content to {difficulty}. The person is {sex}. The subtype is {subtype}.And Make sure to randomize the position of the optimal option on each case cases should not be having the optimal option at the same number"""
            elif question_type == 'study':
                prompt = f"""{prompts['study']} The person's previous responses were as follows:\n{previous_turn_summary}For the case, ask another question with the SAME STRUCTURE based on their previous responses in {language} appropriate for the age {age} with the theme '{subject}'. Set the difficulty of the content to {difficulty}. The person is {sex}. The subtype is {subtype}.And Make sure to randomize the position of the optimal option on each case cases should not be having the optimal option at the same number"""
            elif question_type == 'hiring':
                prompt = f"""{prompts['hiring']} The person's previous responses were as follows:\n{previous_turn_summary}For the case, ask another question with the SAME STRUCTURE based on their previous responses in {language} appropriate for the age {age} with the theme '{subject}'. Set the difficulty of the content to {difficulty}. The person is {sex}. The subtype is {subtype}.And Make sure to randomize the position of the optimal option on each case cases should not be having the optimal option at the same number"""
            logger.debug(f"Follow-up prompt generated: {prompt}")

        response = get_response_gemini(prompt)
        logger.debug(f"Gemini response: {response[:200]}...")

        if not response:
            logger.error("Gemini API returned an empty response.")
            return None, conversation_data

        cleaned_response = clean_response(response)
        list_content = extract_list(cleaned_response)
        logger.debug(f"Extracted list content: {list_content}")

        if list_content:
            try:
                parsed = json.loads(list_content)
                # Do not force a single case—keep all cases returned.
                if not isinstance(parsed, list):
                    parsed = [parsed]
                required_keys = ['case', 'options', 'optimal']
                new_cases = []
                for case in parsed:
                    if not all(key in case for key in required_keys):
                        logger.error(f"Missing required keys in parsed response: {required_keys}")
                        return None, conversation_data
                    case_data = {'case': case['case'], 'optimal': case['optimal'], 'options': []}
                    for option_data in case['options']:
                        option_id = str(uuid.uuid4())
                        option_item = {**option_data, 'option_id': option_id}
                        case_data['options'].append(option_item)
                    new_cases.append(case_data)

                print(f"new cases lenth: ", len(new_cases))
                max = 3
                attempts = 1

                while attempts < 3 and len(new_cases) < max:
                    response = get_response_gemini(prompt)
                    cleaned_response = clean_response(response)
                    list_content = extract_list(cleaned_response)
                    logger.debug(f"Extracted list content: {list_content}")
                    attempts += 1
                    if list_content:
                            parsed = json.loads(list_content)
                            # Do not force a single case—keep all cases returned.
                            if not isinstance(parsed, list):
                                parsed = [parsed]
                            required_keys = ['case', 'options', 'optimal']
                            for case in parsed:
                                if not all(key in case for key in required_keys):
                                    logger.error(f"Missing required keys in parsed response: {required_keys}")
                                    return None, conversation_data
                                case_data = {'case': case['case'], 'optimal': case['optimal'], 'options': []}
                                for option_data in case['options']:
                                    option_id = str(uuid.uuid4())
                                    option_item = {**option_data, 'option_id': option_id}
                                    case_data['options'].append(option_item)
                                new_cases.append(case_data)


                # Save conversation data to JSON file with the structure: { "data": { "cases": [ ... ] } }
                conversation_filepath = output_dir / "conversation.json"
                conversation_data = {'data': {'cases': new_cases}}
                with open(conversation_filepath, 'w') as f:
                    json.dump(conversation_data, f, indent=4)
                logger.debug(f"Conversation data saved to {conversation_filepath}")
                return new_cases, conversation_data

            except json.JSONDecodeError as e:
                logger.exception(f"Error decoding JSON response: {e}, Raw Response: {response}")
                return None, conversation_data
            except Exception as e:
                logger.exception(f"An unexpected error occurred while processing response: {e}")
                return None, conversation_data

        else:
            logger.error("extract_list returned None or empty string.")
            return None, conversation_data
    except Exception as e:
        logger.exception(f"An unexpected error occurred in gen_cases: {e}")
        return None, conversation_data


def generate_product_guidance(problem_statement: str, industry: str, technology: str, target_audience: str) -> dict:
    try:
        prompts_to_generate = {
            "clarify_problem": prompts['clarify_problem'].format(problem_statement=problem_statement, industry=industry, technology=technology),
            "check_duplicates": prompts['check_duplicates'].format(problem_statement=problem_statement),
            "assess_feasibility": prompts['assess_feasibility'].format(problem_statement=problem_statement),
            "suggest_solutions": prompts['suggest_solutions'].format(problem_statement=problem_statement),
            "advice_feedback": prompts['advice_feedback'].format(problem_statement=problem_statement),
            "recommend_tech_stack": prompts['recommend_tech_stack'].format(problem_statement=problem_statement)
        }

        responses = {}
        for key, prompt in prompts_to_generate.items():
            responses[key] = get_response_gemini(prompt)

        return responses
    except Exception as e:
        logger.exception(f"An unexpected error occurred in generate_product_guidance: {e}")
        return {}
