import google.generativeai as genai
import os
from dotenv import load_dotenv

import json

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash-latest")


def get_gemini_response(prompt):
    response = model.generate_content(prompt)
    return response.text.strip()

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

        print("✅ Temizlenmiş JSON:", yanit)

        json_obj = json.loads(yanit)
        return json.dumps(json_obj, ensure_ascii=False)

    except Exception as e:
        print("❌ JSON değerlendirme hatası:", e)
        return json.dumps({
            "puan": 0,
            "geri_bildirim": "AI değerlendirmesi alınamadı. Lütfen tekrar deneyin."
        }, ensure_ascii=False)





