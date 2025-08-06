import os
import json
from datetime import datetime
from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

from gemini_api import (
    evaluate_answer_with_gemini,
    get_gemini_analysis
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ---- Durumlar (Conversation) ----
QA_WAITING = 10  # /qa sonrası kullanıcı cevabını beklerken

class ZorBaRaBot:
    def __init__(self):
        self.app = ApplicationBuilder().token(TOKEN).build()

        # Veri setleri
        self.daily_tasks = self._load_json("static/data/daily_tasks.json")
        self.pedia       = self._load_json("static/data/zorbapedia.json")
        self.qa_questions= self._load_json("static/data/qa_questions.json")

        # Kullanıcı başına durum (demo: bellek içi)
        # { user_id: {
        #     "points": int,
        #     "badge": str|None,
        #     "last_daily_date": "YYYY-MM-DD" or None,
        #     "last_qa_index": int or None,
        #     "chat_history": [str, ...]
        # } }
        self.users = {}

        self._register_handlers()

    # ---------- Yardımcılar ----------
    def _load_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_user(self, user_id):
        if user_id not in self.users:
            self.users[user_id] = {
                "points": 0,
                "badge": None,
                "last_daily_date": None,
                "last_qa_index": None,
                "chat_history": []
            }
        return self.users[user_id]

    def _maybe_award_badge(self, user):
        if user["badge"]:
            return
        if user["points"] >= 70:
            user["badge"] = "🥇 Zorbalık Avcısı"

    # Gün bazlı deterministik görev seçimi (tarihe göre)
    def _daily_index(self, date_str):
        # FNV benzeri basit hash
        h = 2166136261
        for ch in date_str:
            h ^= ord(ch)
            h += (h<<1)+(h<<4)+(h<<7)+(h<<8)+(h<<24)
        return abs(h) % max(1, len(self.daily_tasks))

    # ---------- Kayıt ----------
    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("yardim", self.yardim))
        self.app.add_handler(CommandHandler("gorev", self.gorev))
        self.app.add_handler(CommandHandler("gorev_tamam", self.gorev_tamam))
        self.app.add_handler(CommandHandler("qa", self.qa_ask))
        self.app.add_handler(CommandHandler("pedia", self.pedia_cmd))
        self.app.add_handler(CommandHandler("rozet", self.rozet))

        # QA akışı için Conversation
        qa_conv = ConversationHandler(
            entry_points=[CommandHandler("qa", self.qa_ask)],
            states={
                QA_WAITING: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.qa_answer)]
            },
            fallbacks=[],
            name="qa_conversation",
            persistent=False
        )
        self.app.add_handler(qa_conv)

        # Serbest sohbet (en sonda)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.sohbet))

    # ---------- Komutlar ----------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "👋 *Merhaba! Ben ZorBaRa – Zorbalık Radarım açık, seni dinliyorum.*\n\n"
            "💬 Burada dilediğin gibi yazabilirsin; birlikte çıkar yol buluruz.\n\n"
            "🎯 Başlamak için:\n"
            "• /gorev – *Günün Görevi* (+10 puan)\n"
            "• /qa – *Soru-Cevap (AI değerlendirme)* (+5–20 puan)\n"
            "• /pedia <kelime> – *ZorbaPedia* araması\n"
            "• /rozet – *Puan/Rozet durumun*\n"
            "• /yardim – *Acil hatlar*\n"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def yardim(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🆘 *Acil Yardım Hattı Bilgileri:*\n\n"
            "📞 112 – *Acil Sağlık*\n"
            "📞 155 – *Polis İmdat*\n"
            "📞 183 – *Aile, Kadın, Çocuk Sosyal Destek*\n\n"
            "_Tehlike altındaysan bu numaralardan birini aramaktan çekinme._",
            parse_mode="Markdown"
        )

    # ---- Günün Görevi ----
    async def gorev(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_user(update.effective_user.id)
        today = datetime.now().strftime("%Y-%m-%d")
        idx = self._daily_index(today)
        task = self.daily_tasks[idx]

        # Tamamlama butonu yerine komut akışı (demo basitliği)
        done_hint = ""
        if user["last_daily_date"] == today:
            done_hint = "\n\n✅ *Bugünkü görevi zaten tamamladın.* (+10 puan verilmişti)"
        else:
            done_hint = "\n\nTamamlayınca `/gorev_tamam` yazabilirsin. (+10 puan)"

        text = f"🗓️ *Günün Görevi*\n\n*{task['title']}*\n{task.get('info','')}{done_hint}"
        await update.message.reply_text(text, parse_mode="Markdown")

    async def gorev_tamam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_user(update.effective_user.id)
        today = datetime.now().strftime("%Y-%m-%d")
        if user["last_daily_date"] == today:
            await update.message.reply_text("Bugünün görevi zaten tamamlanmış görünüyor. Yarın yeni görevle devam! 🙌")
            return
        user["last_daily_date"] = today
        user["points"] += 10
        self._maybe_award_badge(user)

        reply = f"🎉 Harika! *+10 puan* kazandın.\nToplam Puan: *{user['points']}*"
        if user["badge"]:
            reply += f"\n\n🏅 Rozetin: *{user['badge']}*"
        await update.message.reply_text(reply, parse_mode="Markdown")

    # ---- QA (Biz soruyoruz, kullanıcı cevaplıyor) ----
    async def qa_ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_user(update.effective_user.id)

        # Rastgele bir soru (üst üste aynı gelmesin)
        import random
        if not self.qa_questions:
            await update.message.reply_text("Şu an soru bulunamadı.")
            return ConversationHandler.END

        idx = random.randrange(len(self.qa_questions))
        if user["last_qa_index"] is not None and len(self.qa_questions) > 1 and idx == user["last_qa_index"]:
            idx = (idx + 1) % len(self.qa_questions)
        user["last_qa_index"] = idx

        soru = self.qa_questions[idx]

        await update.message.reply_text(
            f"🧩 *Soru-Cevap (AI)*\n\n*soru:* {soru}\n\n"
            "_Cevabını bu mesajın altına yaz. (min 20 karakter)_",
            parse_mode="Markdown"
        )
        return QA_WAITING

    async def qa_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_user(update.effective_user.id)
        idx = user.get("last_qa_index")
        if idx is None or idx >= len(self.qa_questions):
            await update.message.reply_text("Önce /qa ile bir soru başlat lütfen.")
            return ConversationHandler.END

        soru = self.qa_questions[idx]
        cevap = update.message.text.strip()
        if len(cevap) < 20:
            await update.message.reply_text("Biraz daha detaylı yazabilir misin? (min 20 karakter)")
            return QA_WAITING

        # Gemini değerlendirme
        try:
            result_json = evaluate_answer_with_gemini(soru, cevap)
            result = json.loads(result_json)
            puan = int(result.get("puan", 0))
            geri = result.get("geri_bildirim", "")
        except Exception:
            puan = 0
            geri = "AI değerlendirmesi alınamadı, tekrar dener misin?"

        # Puan kazancı: 5–20 arası
        kazan = max(5, round(puan * 4))
        user["points"] += kazan
        self._maybe_award_badge(user)

        msg = (
            f"🧠 *AI Değerlendirme:* {puan}/5 ⭐\n"
            f"{geri}\n\n"
            f"➕ *+{kazan} puan*\n"
            f"📊 *Toplam:* {user['points']}"
        )
        if user["badge"]:
            msg += f"\n🏅 *Rozet:* {user['badge']}"

        await update.message.reply_text(msg, parse_mode="Markdown")
        return ConversationHandler.END

    # ---- ZorbaPedia ----
    async def pedia_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args or []
        if not args:
            await update.message.reply_text("Kullanım: `/pedia <anahtar kelime>`\nÖrn: `/pedia şaka`", parse_mode="Markdown")
            return

        q = " ".join(args).lower()
        results = []
        for item in self.pedia:
            haystack = " ".join([
                item.get("title",""),
                item.get("content",""),
                " ".join(item.get("tags",[]))
            ]).lower()
            if q in haystack:
                results.append(item)
            if len(results) >= 3:
                break

        if not results:
            await update.message.reply_text("Sonuç bulunamadı. Başka bir kelime dener misin?")
            return

        for it in results:
            tips = it.get("tips", [])
            tips_txt = "\n".join([f"• {t}" for t in tips[:3]])
            txt = (
                f"📚 *{it.get('title','')}*\n\n"
                f"{it.get('content','')}\n\n"
                f"{tips_txt}"
            )
            await update.message.reply_text(txt, parse_mode="Markdown")

    # ---- Rozet ----
    async def rozet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_user(update.effective_user.id)
        self._maybe_award_badge(user)
        if user["badge"]:
            await update.message.reply_text(
                f"🏅 *Rozetin:* {user['badge']}\n"
                f"📊 Toplam Puanın: *{user['points']}*",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"Henüz rozet kazanmadın.\n"
                f"🎯 Hedef: *70+ puan*\n"
                f"İpuçları: /gorev (günlük +10), /qa (5–20), /pedia ile öğren!",
                parse_mode="Markdown"
            )

    # ---- Serbest Sohbet + eğitim/ acil tespiti ----
    async def sohbet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_user(update.effective_user.id)
        mesaj = update.message.text.strip()

        # geçmişi hazırla (son 8 mesaj)
        hist = user["chat_history"][-8:] if user["chat_history"] else []
        yanit, acil, egitim_oneri = get_gemini_analysis(mesaj, history=hist)

        # yanıtı parça parça gönder
        for par in yanit.split("\n\n"):
            if par.strip():
                await update.message.reply_text(par.strip())

        if acil:
            await update.message.reply_text(
                "🚨 *Bu önemli bir konu olabilir.*\n"
                "Lütfen aşağıdaki hatalardan biriyle iletişime geç:\n\n"
                "📞 183 – Aile, Kadın, Çocuk Sosyal Destek\n"
                "📞 112 – Acil Sağlık\n"
                "📞 155 – Polis İmdat",
                parse_mode="Markdown"
            )

        if egitim_oneri:
            await update.message.reply_text(
                "🎓 Kendini geliştirmek istersen */gorev* ve */qa* ile puan toplayabilir, 70+ olduğunda rozeti kapabilirsin! (/rozet)",
                parse_mode="Markdown"
            )

        # geçmişi güncelle
        user["chat_history"].append(mesaj)
        user["chat_history"].append(yanit)
        # çok uzamasın
        if len(user["chat_history"]) > 12:
            user["chat_history"] = user["chat_history"][-12:]

    # ---------- Çalıştır ----------
    def run(self):
        print("✅ ZorBaRa Telegram Botu başlatıldı.")
        self.app.run_polling()


if __name__ == "__main__":
    bot = ZorBaRaBot()
    bot.run()
