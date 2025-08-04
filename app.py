from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_cors import CORS
import uuid
import json
import os
from functools import wraps
from datetime import timedelta

# ---------------- CONFIG ----------------
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")

# Force secure cookies (for Railway HTTPS)
app.config.update({
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'SESSION_COOKIE_SECURE': True,
    'PERMANENT_SESSION_LIFETIME': timedelta(minutes=30)  # auto-expires in 30 min
})

# Admin credentials
SECRET_CODE = os.getenv("SECRET_CODE", "Amity@Cyber_2024")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Cyber@Admin123")

# Data storage folders
FORMS_DIR = 'forms'
RESPONSES_DIR = 'responses'
os.makedirs(FORMS_DIR, exist_ok=True)
os.makedirs(RESPONSES_DIR, exist_ok=True)

# ---------------- AUTH GUARD ----------------
def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Unauthorized access. Please log in first.", "error")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return wrapped

# ---------------- ROUTES ----------------
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
        session.clear()
        session.permanent = True  # makes session respect lifetime
        session['admin_logged_in'] = True
        return jsonify({"status": "success", "redirect": "/admin_dashboard"})
    return jsonify({"status": "fail"}), 401

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")

# ---------------- FORM CREATION ----------------
@app.route('/create_form', methods=['GET', 'POST'])
@admin_required
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

# ---------------- USER FORM ROUTES ----------------
@app.route('/get_form/<form_id>')
def get_form(form_id):
    path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if not os.path.exists(path):
        return jsonify({"error": "Form not found"}), 404
    with open(path) as f:
        return jsonify(json.load(f))

@app.route('/join_form/<form_id>')
def join_form_with_id(form_id):
    path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if os.path.exists(path):
        return redirect(url_for('user_form', form_id=form_id))
    return "❌ Form not found", 404

@app.route('/user_form/<form_id>')
def user_form(form_id):
    path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if not os.path.exists(path):
        return render_template("user_form.html", error="Form not found.", form=None, questions=None)
    with open(path) as f:
        form_data = json.load(f)
    return render_template("user_form.html", form=form_data, questions=form_data.get("questions", []))

# ---------------- SUBMIT FORM ----------------
@app.route('/submit_form/<form_id>', methods=['POST'])
def submit_form(form_id):
    path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if not os.path.exists(path):
        return render_template("error.html", message="Form not found.")

    with open(path) as f:
        form_data = json.load(f)

    form_answers = request.form
    questions = form_data.get('questions', [])
    score, total, answers = 0, 0, {}

    for q in questions:
        qid = q.get('id')
        qtype = q.get('type', '').lower()
        input_style = q.get('input_style', 'radio')
        marks = int(q.get('marks', 1))
        correct = [c.strip().lower() for c in q.get('correct', []) if isinstance(c, str)]
        base_field = f'question_{qid}'
        total += marks

        if qtype == "mcq" and input_style == "checkbox":
            user_ans = form_answers.getlist(base_field)
            answers[qid] = user_ans
            if sorted([x.strip().lower() for x in user_ans]) == sorted(correct):
                score += marks
        elif qtype == "mcq":
            user_ans = form_answers.get(base_field, "").strip().lower()
            answers[qid] = user_ans
            if user_ans in correct:
                score += marks
        elif qtype == "checkbox":
            user_ans = form_answers.getlist(base_field)
            answers[qid] = user_ans
            if sorted([x.strip().lower() for x in user_ans]) == sorted(correct):
                score += marks
        elif qtype in ["short", "text"]:
            user_ans = form_answers.get(base_field, "").strip().lower()
            answers[qid] = user_ans
            if user_ans in correct:
                score += marks
        else:
            answers[qid] = "Unknown question type"

    response_id = str(uuid.uuid4())
    with open(os.path.join(RESPONSES_DIR, f"{form_id}_{response_id}.json"), 'w') as f:
        json.dump({
            'response_id': response_id,
            'form_id': form_id,
            'answers': answers,
            'score': score,
            'total': total
        }, f, indent=2)

    return render_template("submit_form.html", score=score, total=total)

# ---------------- ADMIN VIEWS ----------------
@app.route('/view_forms')
@admin_required
def view_forms():
    form_ids = []
    for filename in os.listdir(FORMS_DIR):
        if filename.endswith('.json'):
            form_id = filename[:-5]
            with open(os.path.join(FORMS_DIR, filename), 'r') as f:
                title = json.load(f).get('title', 'Untitled')
                form_ids.append((form_id, title))
    return render_template('view_forms.html', forms=form_ids)

@app.route('/delete_form/<form_id>', methods=['POST'])
@admin_required
def delete_form(form_id):
    path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if os.path.exists(path):
        os.remove(path)
        flash(f'Form {form_id} deleted.', 'success')
    else:
        flash(f'Form {form_id} not found.', 'error')
    return redirect(url_for('view_forms'))

@app.route('/view_form_responses/<form_id>')
@admin_required
def view_form_responses(form_id):
    path = os.path.join(FORMS_DIR, f"{form_id}.json")
    if not os.path.exists(path):
        return render_template("error.html", message="Form not found.")

    try:
        with open(path) as f:
            form_data = json.load(f)
    except Exception as e:
        return render_template("error.html", message=f"Error reading form: {e}")

    questions = form_data.get('questions', [])
    responses = []
    for filename in os.listdir(RESPONSES_DIR):
        if filename.startswith(form_id):
            try:
                with open(os.path.join(RESPONSES_DIR, filename)) as rf:
                    responses.append(json.load(rf))
            except:
                continue
    return render_template("form_responses.html", form_id=form_id, questions=questions, responses=responses)

@app.route('/delete_response/<form_id>/<response_id>', methods=['POST'])
@admin_required
def delete_response(form_id, response_id):
    path = os.path.join(RESPONSES_DIR, f"{form_id}_{response_id}.json")
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for('view_form_responses', form_id=form_id))

# ---------------- RUN ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
