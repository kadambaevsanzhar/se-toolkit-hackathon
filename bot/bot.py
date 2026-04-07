#!/usr/bin/env python3
"""Minimal Telegram Bot for AI Homework Grading."""

import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

class HomeworkGraderBot:
    """Minimal Telegram bot for homework grading."""

    def __init__(self):
        if not TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN environment variable is required")

        self.backend_url = BACKEND_URL.rstrip('/')
        logger.info(f"Bot initialized with backend URL: {self.backend_url}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text(
            "Send me a photo of your homework and I'll analyze it!\n\n"
            "Just upload an image and I'll provide feedback with a score."
        )

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages."""
        try:
            # Get the largest photo size
            photo = update.message.photo[-1]

            # Download the photo
            file = await context.bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()

            # Send to backend for analysis
            await update.message.reply_text("Analyzing your homework...")

            result = self.analyze_homework(photo_bytes)

            # Format and send response
            response = self.format_result(result)
            await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Error processing photo: {e}")
            await update.message.reply_text(
                "Sorry, I couldn't analyze your homework. Please try again."
            )

    def analyze_homework(self, photo_bytes):
        """Send photo to backend for analysis."""
        try:
            files = {'file': ('homework.jpg', photo_bytes, 'image/jpeg')}
            response = requests.post(f"{self.backend_url}/analyze", files=files, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Backend error: {response.status_code} - {response.text}")
                raise Exception(f"Backend returned {response.status_code}")

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            raise Exception("Failed to connect to analysis service")

    def format_result(self, result):
        """Format analysis result for Telegram."""
        try:
            analysis = result.get('result', {})
            score = analysis.get('suggested_score', 'N/A')
            feedback = analysis.get('short_feedback', 'Analysis completed')

            response = f"📊 Score: {score}/10\n\n💬 {feedback}"

            # Add strengths if present
            strengths = analysis.get('strengths', [])
            if strengths:
                response += f"\n\n✅ Strengths:\n" + "\n".join(f"• {s}" for s in strengths[:3])

            # Add mistakes if present
            mistakes = analysis.get('mistakes', [])
            if mistakes:
                response += f"\n\n⚠️ Areas to improve:\n" + "\n".join(f"• {m}" for m in mistakes[:3])

            return response

        except Exception as e:
            logger.error(f"Error formatting result: {e}")
            return "Analysis completed, but there was an error formatting the results."

def main():
    """Run the bot."""
    bot = HomeworkGraderBot()

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))

    logger.info("Bot starting...")
    application.run_polling()

if __name__ == "__main__":
    main()