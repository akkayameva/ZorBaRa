import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from google.generativeai.types import GenerationConfig

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config=GenerationConfig(
        temperature=1.0,
        top_p=1.0,
        max_output_tokens=1024
    )
)

def evaluate_answer_with_gemini(soru, cevap):
    prompt = (
        f"Kullanıcının sorduğu görev: \"{soru}\"\n"
        f"Verdiği cevap: \"{cevap}\"\n\n"
        "Sen bir çocuk psikolojisi uzmanı gibi davran. "
        "Bu cevabı değerlendir: empati, farkındalık ve duygu anlayışı açısından. "
        "1 ila 5 arasında bir puan ver.\n"
        "Yanıtta sadece geçerli bir JSON döndür. Açıklama yapma. Sadece şunu ver:\n"
        "{\n  \"puan\": <1-5>,\n  \"geri_bildirim\": \"...\"\n}"
    )
    try:
        response = model.generate_content(prompt)
        yanit = response.text.strip()
        if yanit.startswith("```"):
            yanit = yanit.strip("`")
            if "json" in yanit:
                yanit = yanit.replace("json", "", 1).strip()
        json_obj = json.loads(yanit)
        return json.dumps(json_obj, ensure_ascii=False)
    except Exception as e:
        print("❌ JSON değerlendirme hatası:", e)
        return json.dumps({
            "puan": 0,
            "geri_bildirim": "AI değerlendirmesi alınamadı. Lütfen tekrar deneyin."
        }, ensure_ascii=False)

def get_gemini_analysis(prompt, history=None):
    """
    Kullanıcının mesajına empatik yanıt, acil durum tespiti ve eğitim ihtiyacı analizi üretir.
    """
    if history is None:
        history = []

    messages = []
    for i, msg in enumerate(history):
        role = "user" if i % 2 == 0 else "model"
        messages.append({"role": role, "parts": [msg]})
    messages.append({"role": "user", "parts": [prompt]})

    full_prompt = (
        f"Kullanıcının mesajı:\n\"{prompt}\"\n\n"
        "1. Pedagojik ve empatik bir dille, çocuğa/ergene hitap ederek yanıt ver.Acınası bir dille olmasın samimi ol ve bunun zorbalık olduğunu tanımla\n"
        "2. Eğer mesajda intihar, taciz, ciddi depresyon veya şiddet tehdidi varsa şunu sona ekle:\n"
        "ACİL_DURUM: EVET\nYOKSA: ACİL_DURUM: HAYIR\n"
        "Eğer kullanıcı bu mesajda doğrudan eğitim istiyorsa şunu ekle:\n"
        "EGITIM_ONERI: EVET\nYOKSA: EGITIM_ONERI: HAYIR\n"
        "\nYalnızca yanıt + 2 etiketi döndür (ek açıklama yok).\n"
    )

    try:
        convo = model.start_chat(history=messages)
        response = convo.send_message(full_prompt)
        yanit = response.text.strip()

        emergency = "ACİL_DURUM: EVET" in yanit
        egitim = "EGITIM_ONERI: EVET" in yanit

        yanit = yanit.replace("ACİL_DURUM: EVET", "").replace("ACİL_DURUM: HAYIR", "")
        yanit = yanit.replace("EGITIM_ONERI: EVET", "").replace("EGITIM_ONERI: HAYIR", "").strip()

        return yanit, emergency, egitim
    except Exception as e:
        print("❌ Yanıt analiz hatası:", e)
        return "Bir sorun oluştu. Lütfen tekrar dene.", False, False
