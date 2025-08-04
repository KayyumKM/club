from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_cors import CORS
import uuid
import json
import os


app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")


# Admin credentials and secret code
SECRET_CODE = "Amity@Cyber_2024"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Cyber@Admin123"

# Directories for forms and responses
FORMS_DIR = 'forms'
RESPONSES_DIR = 'responses'

os.makedirs(FORMS_DIR, exist_ok=True)
os.makedirs(RESPONSES_DIR, exist_ok=True)


@app.route('/')
def home():
    return render_template("index.html")

@app.route('/check_secret_code', methods=['POST'])
def check_secret_code():
    data = request.get_json()
    if data.get('code') == SECRET_CODE:
        return jsonify({"status": "success"})
    return jsonify({"status": "fail"}), 403

@app.route('/admin_login', methods=['POST'])
def admin_login():
    data = request.get_json()
    if data.get('username') == ADMIN_USERNAME and data.get('password') == ADMIN_PASSWORD:
        return jsonify({"status": "success", "redirect": "/admin_dashboard"})
    return jsonify({"status": "fail"}), 401

@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route('/create_form', methods=['GET', 'POST'])
def create_form():
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            if not data or 'title' not in data or 'questions' not in data:
                return jsonify({"status": "fail", "message": "Invalid data format"})

            form_id = str(uuid.uuid4())[:8]
            form_data = {
                "id": form_id,
                "title": data['title'],
                "questions": data['questions']
            }

            with open(os.path.join(FORMS_DIR, f"{form_id}.json"), 'w') as f:
                json.dump(form_data, f, indent=2)

            return jsonify({"status": "success", "form_id": form_id})

        except Exception as e:
            return jsonify({"status": "fail", "message": str(e)})

    return render_template("create_form.html")


@app.route('/get_form/<form_id>')
def get_form(form_id):
    form_path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if not os.path.exists(form_path):
        return jsonify({"error": "Form not found"}), 404

    with open(form_path) as f:
        form_data = json.load(f)

    return jsonify(form_data)

@app.route('/join_form/<string:form_id>', methods=['GET'])
def join_form_with_id(form_id):
    form_path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if os.path.exists(form_path):
        return redirect(url_for('user_form', form_id=form_id))
    else:
        return "❌ Form not found", 404

######
@app.route('/user_form/<form_id>')
def user_form(form_id):
    form_path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if not os.path.exists(form_path):
        return render_template("user_form.html", error="Form not found.", form=None, questions=None)

    with open(form_path) as f:
        form_data = json.load(f)

    questions = form_data.get("questions", [])
    return render_template("user_form.html", form=form_data, questions=questions)

@app.route('/submit_form/<form_id>', methods=['POST'])
def submit_form(form_id):
    form_path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if not os.path.exists(form_path):
        return render_template("error.html", message="Form not found.")

    with open(form_path) as f:
        form_data = json.load(f)

    form_answers = request.form
    questions = form_data.get('questions', [])
    score = 0
    total = 0
    answers = {}

    for q in questions:
        qid = q.get('id')
        qtype = q.get('type', '').lower()
        input_style = q.get('input_style', 'radio')
        marks = int(q.get('marks', 1))
        correct = q.get('correct', [])
        required = q.get('required', False)

        # Normalize correct answers
        correct_normalized = [c.strip().lower() for c in correct if isinstance(c, str)]
        base_field = f'question_{qid}'
        total += marks

        # ----- MCQ -----
        if qtype == "mcq":
            if input_style == "checkbox":
                user_ans_list = form_answers.getlist(base_field)  # fix: do not use '[]'
                user_ans_list_clean = [a.strip().lower() for a in user_ans_list]
                answers[qid] = user_ans_list
                if sorted(user_ans_list_clean) == sorted(correct_normalized):
                    score += marks
            else:  # radio
                user_ans = form_answers.get(base_field, "").strip().lower()
                answers[qid] = user_ans
                if user_ans in correct_normalized:
                    score += marks

        # ----- Checkbox-type (if not MCQ) -----
        elif qtype == "checkbox":
            user_ans_list = form_answers.getlist(base_field)
            user_ans_list_clean = [a.strip().lower() for a in user_ans_list]
            answers[qid] = user_ans_list
            if sorted(user_ans_list_clean) == sorted(correct_normalized):
                score += marks

        # ----- Short/Text -----
        elif qtype in ("short", "text"):
            user_ans = form_answers.get(base_field, "").strip().lower()
            answers[qid] = user_ans
            if correct_normalized and user_ans in correct_normalized:
                score += marks

        # ----- Unknown Type -----
        else:
            answers[qid] = "Unknown question type"

    # Debug print (optional)
    print("User Answers:", answers)
    print("Score:", score, "/", total)

    # Save response
    response_id = str(uuid.uuid4())
    response_data = {
        'response_id': response_id,
        'form_id': form_id,
        'answers': answers,
        'score': score,
        'total': total
    }

    with open(os.path.join(RESPONSES_DIR, f"{form_id}_{response_id}.json"), 'w') as f:
        json.dump(response_data, f, indent=2)

    return render_template("submit_form.html", score=score, total=total)




@app.route('/view_forms')
def view_forms():
    form_ids = []
    for filename in os.listdir(FORMS_DIR):
        if filename.endswith('.json'):
            form_id = filename[:-5]
            with open(os.path.join(FORMS_DIR, filename), 'r') as f:
                data = json.load(f)
                title = data.get('title', 'Untitled')
                form_ids.append((form_id, title))
    return render_template('view_forms.html', forms=form_ids)

@app.route('/delete_form/<form_id>', methods=['POST'])
def delete_form(form_id):
    path = os.path.join(FORMS_DIR, f'{form_id}.json')
    if os.path.exists(path):
        os.remove(path)
        flash(f'Form {form_id} deleted successfully.', 'success')
    else:
        flash(f'Form {form_id} not found.', 'error')
    return redirect(url_for('view_forms'))

@app.route('/view_form_responses/<form_id>')
def view_form_responses(form_id):
    form_path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if not os.path.exists(form_path):
        return render_template("error.html", message="Form not found.")

    with open(form_path) as f:
        form_data = json.load(f)

    questions = form_data.get('questions', [])
    response_files = [f for f in os.listdir(RESPONSES_DIR) if f.startswith(form_id)]
    responses = []

    for filename in response_files:
        with open(os.path.join(RESPONSES_DIR, filename)) as rf:
            data = json.load(rf)
            responses.append(data)

    return render_template("form_responses.html", form_id=form_id, questions=questions, responses=responses)


@app.route('/delete_response/<form_id>/<response_id>', methods=['POST'])
def delete_response(form_id, response_id):
    path = os.path.join(RESPONSES_DIR, f"{form_id}_{response_id}.json")
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for('view_form_responses', form_id=form_id))

if __name__ == '__main__':
    app.run(debug=True)

