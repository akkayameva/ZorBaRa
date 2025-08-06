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

def get_gemini_response_with_emergency_flag(prompt):
    full_prompt = (
        f"Kullanıcının mesajı:\n\"{prompt}\"\n\n"
        "Sen bir çocuk ve genç destek hattında görevli, çok duyarlı ve yargılamayan bir yapay zekasın.\n"
        "Kullanıcın şu anda üzgün, kafası karışık, kırılmış veya çaresiz hissediyor olabilir.\n"
        "Senin görevin onun mesajını ciddiye almak, ona yalnız olmadığını hissettirmek ve nazikçe destek sunmak.\n\n"

        "Cevap verirken:\n"
        "- Karşındaki bir danışan değil, duygusal desteğe ihtiyacı olan biri. Ona bir arkadaş gibi yaklaş.\n"
        "- Samimi, sade ve içten yaz. ‘Anlıyorum, bu çok zor olabilir…’ gibi yumuşak girişler kullan.\n"
        "- Gerektiğinde madde madde çözüm önerileri sun, ama önce duygusunu karşıla.\n"
        "- Gerekli yerlerde sade ve anlamlı emojiler kullan (🤝, 💡, 📷, 🚫, ❤️, ☀️, 💬). Aşırıya kaçma.\n"
        "- Kısa paragraflar kullan. Her paragraf bir düşünce veya duygu taşısın.\n"
        "- Asla yargılayıcı olma, asla ‘şunu yapmalısın’ deme. Yönlendirme değil, eşlik et.\n"
        "- Cevabının sonunda 'İstersen biraz daha konuşabiliriz 💬' gibi bir açık kapı bırak.\n\n"

        "Ayrıca bu mesaj sence aşağıdaki kritik durumlardan birini içeriyor mu?\n"
        "- İntihar düşüncesi\n- Taciz, istismar\n- Şiddet tehdidi\n- Ciddi depresyon belirtisi\n\n"
        "Eğer böyle bir durum varsa, sadece şunu en alta ekle:\n"
        "ACİL_DURUM: EVET\n\n"
        "Eğer yoksa:\n"
        "ACİL_DURUM: HAYIR\n"
    )

    try:
        response = model.generate_content(full_prompt)
        full_response = response.text.strip()
        emergency = "ACİL_DURUM: EVET" in full_response
        reply = full_response.replace("ACİL_DURUM: EVET", "").replace("ACİL_DURUM: HAYIR", "").strip()
        print("📤 Gemini yanıtı:\n", full_response)
        return reply, emergency
    except Exception as e:
        print("❌ Emergency kontrol hatası:", e)
        return "Bir sorun oluştu. Lütfen tekrar dene.", False

def get_gemini_response_with_context(prompt, history=None):
    """
    Multi-turn chat için bağlamlı cevap üretir.
    history: ["kullanıcı mesajı", "bot cevabı", "kullanıcı mesajı", ...]
    """
    if history is None:
        history = []

    messages = []
    for i, msg in enumerate(history):
        role = "user" if i % 2 == 0 else "model"
        messages.append({"role": role, "parts": [msg]})
    messages.append({"role": "user", "parts": [prompt]})

    try:
        convo = model.start_chat(history=messages)
        response = convo.send_message(prompt)
        yanit = response.text.strip()
        emergency = "ACİL_DURUM: EVET" in yanit
        yanit = yanit.replace("ACİL_DURUM: EVET", "").replace("ACİL_DURUM: HAYIR", "").strip()
        return yanit, emergency
    except Exception as e:
        print("❌ Multi-turn chat hatası:", e)
        return "Bir sorun oluştu. Lütfen tekrar dene.", False
