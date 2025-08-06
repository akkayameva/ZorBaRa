from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
from gemini_api import get_gemini_analysis, evaluate_answer_with_gemini
import json

app = Flask(__name__)
app.secret_key = "zorbara-secret"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
CORS(app)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/egitim")
def egitim():
    return render_template("egitim.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    if not user_input:
        return jsonify({"error": "Mesaj boş olamaz"}), 400

    # Önceki sohbet geçmişini al (çok adımlı bağlam için)
    history = session.get("chat_history", [])

    # çok yönlü analiz  yanıt, acil durum, eğitim önerisi
    reply, emergency, education_needed = get_gemini_analysis(user_input, history)


    history.append(user_input)
    history.append(reply)
    session["chat_history"] = history[-10:]

    return jsonify({
        "reply": reply,
        "emergency": emergency,
        "show_education_prompt": education_needed
    })

@app.route("/rozet")
def rozet():
    return render_template("rozet.html")

@app.route("/evaluate", methods=["POST"])
def evaluate():
    data = request.get_json()
    soru = data.get("soru")
    cevap = data.get("cevap")
    if not soru or not cevap:
        return jsonify({"error": "Soru veya cevap eksik."}), 400

    ai_feedback_raw = evaluate_answer_with_gemini(soru, cevap)
    try:
        ai_feedback = json.loads(ai_feedback_raw)
        return jsonify({"ai_feedback": ai_feedback})
    except json.JSONDecodeError:
        return jsonify({"error": "Gemini'den geçerli JSON gelmedi."}), 500

if __name__ == "__main__":
    app.run(debug=True)
