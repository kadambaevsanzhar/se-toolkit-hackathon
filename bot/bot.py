#!/usr/bin/env python3
"""Minimal Telegram Bot for AI Homework Grading with status indicators."""

import os
import logging
import requests
import asyncio
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
ANALYSIS_TIMEOUT = int(os.getenv("ANALYSIS_TIMEOUT", "150"))

# Display timezone for Telegram — configurable via DISPLAY_TZ env var
try:
    from zoneinfo import ZoneInfo
    DISPLAY_TZ = ZoneInfo(os.getenv("DISPLAY_TZ", "UTC"))
except ImportError:
    DISPLAY_TZ = timezone.utc


def format_telegram_time(iso_string: str) -> str:
    """Convert ISO 8601 UTC time to DISPLAY_TZ for readable output."""
    if not iso_string:
        return '—'
    utc = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    local = utc.astimezone(DISPLAY_TZ)
    return local.strftime('%d %b %Y, %H:%M')


class HomeworkGraderBot:
    """Telegram bot for homework grading with history and status indicators."""

    def __init__(self):
        if not TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN environment variable is required")

        self.backend_url = BACKEND_URL.rstrip('/')
        logger.info("Bot initialized with backend URL: %s", self.backend_url)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text(
            "Send me a photo of your homework and I'll analyze it!\n\n"
            "Commands:\n"
            "📷 Send a photo — get instant feedback\n"
            "📋 /history — view your recent submissions"
        )

    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command — show user's own submissions."""
        chat_id = update.effective_chat.id
        logger.info("[Bot] /history requested by chat_id=%s", chat_id)

        try:
            headers = {
                'X-Owner-ID': str(chat_id),
                'X-Source': 'telegram',
            }
            resp = requests.get(f"{self.backend_url}/history", headers=headers, timeout=10)

            if resp.status_code != 200:
                await update.message.reply_text("Failed to load history. Please try again.")
                return

            items = resp.json()
            if not items:
                await update.message.reply_text("📋 No submissions found yet. Send me a photo to get started!")
                return

            # Show latest 5 submissions
            recent = items[:5]
            msg = f"📋 Your recent submissions (showing {len(recent)} of {len(items)}):\n\n"
            for item in recent:
                score = item.get('suggested_score', '—')
                feedback = item.get('short_feedback', '') or '(No feedback)'
                date = format_telegram_time(item.get('created_at', ''))
                student = item.get('student_name', '')
                topic_parts = [t for t in [item.get('subject'), item.get('topic'), item.get('task_title')] if t]
                topic_str = ' | '.join(topic_parts)

                msg += f"📝 {date}\n"
                if student:
                    msg += f"   👤 {student}\n"
                if topic_str:
                    msg += f"   📂 {topic_str}\n"
                msg += f"   Score: {score}/10\n"
                msg += f"   {feedback[:80]}\n\n"

            if len(items) > 5:
                msg += f"... and {len(items) - 5} more submission(s)"

            await update.message.reply_text(msg)

        except Exception as e:
            logger.error("[Bot] /history error for chat_id=%s: %s", chat_id, e)
            await update.message.reply_text("Sorry, I couldn't load your history. Please try again.")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages with full status indicators."""
        chat_id = update.effective_chat.id
        msg = None  # Reference to status message for editing

        try:
            # Get the largest photo size
            photo = update.message.photo[-1]

            # Download the photo
            file = await context.bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()

            # Stage 1: Immediately acknowledge receipt
            status_msg = "📥 Photo received. Starting analysis..."
            msg = await update.message.reply_text(status_msg)
            logger.info("[Bot] Photo received from chat_id=%s, sent status: %s", chat_id, status_msg)

            # Brief pause to show progress to user
            await asyncio.sleep(0.5)

            # Stage 2: Show analyzing status
            analyzing_msg = "⏳ Analyzing your homework...\n\nThis may take 1-2 minutes. Please wait..."
            await msg.edit_text(analyzing_msg)
            logger.info("[Bot] Editing status to: %s", analyzing_msg)

            # Send to backend for analysis (blocking call)
            result = self.analyze_homework(photo_bytes, chat_id)

            # Stage 3: Show result or failure
            response_text = self.format_result(result)
            await msg.edit_text(response_text)
            logger.info("[Bot] Analysis complete for chat_id=%s", chat_id)

        except Exception as e:
            logger.error("[Bot] Error processing photo from chat_id=%s: %s", chat_id, e)
            error_text = (
                "❌ Analysis failed.\n\n"
                "There was an error processing your homework. Please try again later.\n\n"
                f"Details: {str(e)[:100]}"
            )
            if msg:
                await msg.edit_text(error_text)
            else:
                await update.message.reply_text(error_text)

    def analyze_homework(self, photo_bytes, chat_id):
        """Send photo to backend for analysis with owner isolation."""
        files = {'file': ('homework.jpg', photo_bytes, 'image/jpeg')}
        headers = {
            'X-Owner-ID': str(chat_id),
            'X-Source': 'telegram',
        }
        logger.info(
            "[Bot] Sending to backend: owner_id=%s, source=telegram, timeout=%ds",
            chat_id, ANALYSIS_TIMEOUT,
        )
        response = requests.post(
            f"{self.backend_url}/analyze",
            files=files,
            headers=headers,
            timeout=ANALYSIS_TIMEOUT,
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(
                "[Bot] Backend error: %d — %s",
                response.status_code, response.text[:300],
            )
            raise Exception(f"Backend returned {response.status_code}: {response.text[:200]}")

    def format_result(self, result):
        """Format analysis result for Telegram with full structured feedback."""
        try:
            analysis = result.get('result', {})
            if not analysis:
                return "Analysis completed but returned empty result."

            # Handle non-academic rejection
            if analysis.get('is_academic_submission') is False:
                reason = analysis.get('short_feedback', 'The image does not appear to contain academic content.')
                return (
                    f"📷 Not an Academic Submission\n\n"
                    f"{reason}\n\n"
                    f"Please send a photo of:\n"
                    f"• Homework assignment\n"
                    f"• Written solution or answer\n"
                    f"• Worksheet or notebook page\n"
                    f"• Any school/university task"
                )

            student = analysis.get('student_name')
            topic_parts = [t for t in [analysis.get('subject'), analysis.get('topic'), analysis.get('task_title')] if t]
            is_preliminary = analysis.get('is_preliminary', False) or analysis.get('analysis_status') == 'validator_failed'
            is_validated = analysis.get('analysis_status') == 'success' and analysis.get('validation_status') == 'validated'

            response_parts = []

            # Validation status header — honest rendering
            if is_preliminary:
                response_parts.append("⚠️ Preliminary analysis completed")
                response_parts.append("Final validation was unavailable — please review the result carefully")
            elif is_validated:
                response_parts.append("✅ Validated analysis completed")
            else:
                response_parts.append("ℹ️ Analysis completed")

            if student:
                response_parts.append(f"👤 Student: {student}")
            if topic_parts:
                response_parts.append(f"📂 {' | '.join(topic_parts)}")

            feedback = analysis.get('short_feedback', 'Analysis completed')
            if analysis.get('suggested_score') is not None and analysis.get('max_score') is not None:
                score = analysis.get('suggested_score', 'N/A')
                max_score = analysis.get('max_score', 10)
                score_label = "Preliminary Score" if is_preliminary else "Score"
                response_parts.append(f"📊 {score_label}: {score}/{max_score}")
            response_parts.append(f"💬 {feedback}")

            # Strengths
            strengths = analysis.get('strengths', [])
            if strengths:
                response_parts.append("\n✅ Strengths:")
                response_parts.extend(f"• {s}" for s in strengths[:3])

            # Mistakes
            mistakes = analysis.get('mistakes', [])
            if mistakes:
                response_parts.append("\n⚠️ Areas to improve:")
                response_parts.extend(f"• {m}" for m in mistakes[:3])

            detailed_mistakes = analysis.get('detailed_mistakes', [])
            if detailed_mistakes:
                first = detailed_mistakes[0]
                location = first.get('location')
                what = first.get('what')
                why = first.get('why')
                how_to_fix = first.get('how_to_fix')
                if location or what:
                    response_parts.append("\n🔎 Main issue:")
                    if location:
                        response_parts.append(f"• Where: {location}")
                    if what:
                        response_parts.append(f"• What: {what}")
                    if why:
                        response_parts.append(f"• Why: {why}")
                    if how_to_fix:
                        response_parts.append(f"• Fix: {how_to_fix}")

            # Improvement suggestion
            suggestions = analysis.get('improvement_suggestions', [])
            if suggestions:
                response_parts.append("\n💡 How to improve:")
                response_parts.extend(f"• {s}" for s in suggestions[:3])

            # Next steps
            next_steps = analysis.get('next_steps', [])
            if next_steps:
                response_parts.append("\n📚 What to practice next:")
                response_parts.extend(f"• {s}" for s in next_steps[:3])

            return "\n".join(response_parts)

        except Exception as e:
            logger.error("Error formatting result: %s", e)
            return "Analysis completed, but there was an error formatting the results."


def main():
    """Run the bot."""
    bot = HomeworkGraderBot()

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("history", bot.history))
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))

    logger.info("Bot starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
