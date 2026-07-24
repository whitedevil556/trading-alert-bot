# 🚀 instant test command (मार्केट क्लोजिंग टेस्टसाठी)
@bot.message_handler(commands=['instant_test'])
def instant_test_alert(message):
    if str(message.chat.id) == str(ADMIN_CHAT_ID):
        bot.send_message(ADMIN_CHAT_ID, "⚡ **झटपट ऑटो-अलर्ट टेस्ट सुरू करत आहे...**", parse_mode="Markdown")
        
        subs = load_subscribers()
        if not subs:
            bot.send_message(ADMIN_CHAT_ID, "❌ डेटाबेसमध्ये एकही सबस्क्रायबर सापडला नाही.")
            return

        test_msg = (
            "🧪 **LIVE AUTO-ALERT TEST** 🚀\n"
            "───────────────────\n"
            "📊 **मार्केट क्लोजिंग अलर्ट सिस्टीम चेक**\n\n"
            "तुमच्या बॉटची ऑटो-अलर्ट सिस्टीम १००% अचूक काम करत आहे! ✅"
        )

        sent_count = 0
        for cid in subs.keys():
            try:
                bot.send_message(cid, test_msg, parse_mode="Markdown")
                sent_count += 1
                time.sleep(0.2)
            except Exception as e:
                print(f"Error sending to {cid}: {e}")

        bot.send_message(
            ADMIN_CHAT_ID, 
            f"🎉 **टेस्टिंग यशस्वी!**\n\nएकूण **{sent_count}** सबस्क्रायबर्सना लाईव्ह मेसेज पोहोचला आहे! 🚀", 
            parse_mode="Markdown"
        )
