import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes
)
from gemini_api import evaluate_answer_with_gemini, get_gemini_analysis

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

EGITIM = 1

class ZorBaRaBot:
    def __init__(self):
        self.app = ApplicationBuilder().token(TOKEN).build()
        self.gorevler = self._load_gorevler()
        self.kullanici_durum = {}
        self.sohbet_gecmisi = {}
        self._register_handlers()

    def _load_gorevler(self):
        with open("static/data/egitim_gorevleri.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("yardim", self.yardim))

        egitim_conv = ConversationHandler(
            entry_points=[CommandHandler("egitim", self.egitim)],
            states={EGITIM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.gorev_cevapla)]},
            fallbacks=[]
        )
        self.app.add_handler(egitim_conv)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.sohbet))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        mesaj = (
            "👋 *Merhaba! Ben ZorBaRa – Zorbalık Radarım açık, seni dinliyorum.*\n\n"
            "💬 Burası senin güvenli alanın. İstersen yaşadıklarını paylaşabilir, ister sadece sohbet edebilirsin.\n\n"
            "🧠 Ayrıca senin için küçük görevler hazırladım. /egitim komutu ile başlayabilirsin!"
        )
        await update.message.reply_text(mesaj, parse_mode="Markdown")

    async def yardim(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🖘 *Acil Yardım Hattı Bilgileri:*\n\n"
            "📞 112 – Acil Sağlık\n"
            "📞 155 – Polis İmdat\n"
            "📞 183 – Aile, Kadın, Çocuk Sosyal Destek\n\n"
            "Lütfen bir tehlike altındaysan bu numaralardan birini aramaktan çekinme.",
            parse_mode="Markdown"
        )

    async def egitim(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.kullanici_durum[user_id] = {"gorev_index": 0, "puanlar": []}
        await self._gorev_gonder(update, user_id)
        return EGITIM

    async def _gorev_gonder(self, update, user_id):
        durum = self.kullanici_durum[user_id]
        index = durum["gorev_index"]

        if index >= len(self.gorevler):
            await self._egitim_tamamla(update, user_id)
            return ConversationHandler.END

        gorev = self.gorevler[index]
        mesaj = f"*{gorev.get('title', '')}*\n{gorev.get('content', '')}"
        if gorev.get("info"):
            mesaj += f"\n\n📌_{gorev['info']}_"
        await update.message.reply_text(mesaj, parse_mode="Markdown")

        if gorev.get("type") == "end":
            durum["gorev_index"] += 1
            await self._egitim_tamamla(update, user_id)
            return ConversationHandler.END

    async def gorev_cevapla(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        durum = self.kullanici_durum.get(user_id)
        if not durum:
            await update.message.reply_text("Bir sorun oluştu. Lütfen /egitim komutu ile tekrar başlat.")
            return ConversationHandler.END

        cevap = update.message.text.strip()
        index = durum["gorev_index"]
        gorev = self.gorevler[index]
        soru = gorev.get("content", "")

        result_json = evaluate_answer_with_gemini(soru, cevap)
        result = json.loads(result_json)
        puan = result.get("puan", 0)
        geri_bildirim = result.get("geri_bildirim", "")

        durum["puanlar"].append(puan)
        durum["gorev_index"] += 1

        yanit = f"🧠 *AI Değerlendirme: {puan}/5*\n{geri_bildirim}"
        await update.message.reply_text(yanit, parse_mode="Markdown")

        if durum["gorev_index"] >= len(self.gorevler):
            await self._egitim_tamamla(update, user_id)
            return ConversationHandler.END
        else:
            await self._gorev_gonder(update, user_id)
            return EGITIM

    async def _egitim_tamamla(self, update, user_id):
        puanlar = self.kullanici_durum[user_id]["puanlar"]
        ort = sum(puanlar) / len(puanlar) if puanlar else 0

        if ort >= 4.5:
            rozet = "🥇 *Empati Ustası Rozeti*"
        elif ort >= 3:
            rozet = "🥈 *Farkındalık Yolcusu Rozeti*"
        else:
            rozet = "🥉 *Yeni Başlayan Rozeti*"

        await update.message.reply_text(
            f"🎉 *Eğitim Tamamlandı!*\n\n"
            f"📊 Ortalama Puan: {ort:.1f} / 5\n"
            f"🏅 Kazandığın Rozet: {rozet}\n\n"
            "💬 Sohbete devam edebilir veya tekrar /egitim ile görev yapabilirsin.",
            parse_mode="Markdown"
        )
        del self.kullanici_durum[user_id]

    async def sohbet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        mesaj = update.message.text.strip()

        self.sohbet_gecmisi.setdefault(user_id, []).append(mesaj)
        if len(self.sohbet_gecmisi[user_id]) > 10:
            self.sohbet_gecmisi[user_id] = self.sohbet_gecmisi[user_id][-10:]

        history = self.sohbet_gecmisi[user_id][:-1]
        yanit, acil, egitim = get_gemini_analysis(mesaj, history)

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

        if egitim:
            await update.message.reply_text(
                "🎓 Kendini geliştirmek istersen /egitim yazarak görevlerle başlayabilirsin!"
            )

        self.sohbet_gecmisi[user_id].append(yanit)

    def run(self):
        print("✅ ZorBaRa Telegram Botu başlatıldı.")
        self.app.run_polling()

if __name__ == "__main__":
    bot = ZorBaRaBot()
    bot.run()
