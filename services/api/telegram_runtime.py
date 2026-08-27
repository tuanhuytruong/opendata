"""Optional polling runtime for the OpenData Telegram report bot.

Run only after setting TELEGRAM_BOT_TOKEN in ignored .env.local or the environment:
    python -m telegram_runtime
"""
from __future__ import annotations

import io
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from main import ChartRequest, ReportRequest, build_report, ingest_dataset
from run_store import redacted_error
from telegram_adapter import OutgoingMessage, TelegramReportService


def render_report(run_id: str, charts: list[ChartRequest]) -> str:
    response = build_report(run_id, ReportRequest(charts=charts))
    return bytes(response.body).decode("utf-8")


service = TelegramReportService(render_report)
TELEGRAM_DOWNLOAD_LIMIT = 20 * 1024 * 1024


async def send_message(update: Update, outgoing: OutgoingMessage) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(outgoing.text)
    if outgoing.report_html:
        payload = io.BytesIO(outgoing.report_html.encode("utf-8"))
        payload.name = "opendata-report.html"
        await message.reply_document(document=payload, caption="Validated, self-contained HTML report")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    message = update.effective_message
    if chat is None or message is None or message.text is None:
        return
    await send_message(update, service.handle_text(chat.id, message.text))


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    message = update.effective_message
    document = message.document if message else None
    if chat is None or document is None:
        return
    if document.file_size and document.file_size > TELEGRAM_DOWNLOAD_LIMIT:
        await send_message(update, OutgoingMessage("Telegram bot downloads are limited to 20 MB. Use the web workspace for larger files (up to 100 MB)."))
        return
    try:
        remote_file = await document.get_file()
        raw = bytes(await remote_file.download_as_bytearray())
        profile = ingest_dataset(document.file_name or "upload", raw)
        outgoing = service.attach_dataset(chat.id, profile)
    except Exception as error:  # Transport boundary: never include raw file data or driver details.
        outgoing = OutgoingMessage(f"I could not profile that document: {redacted_error(error)}")
    await send_message(update, outgoing)


def create_application(token: str) -> Application:
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("report", on_text))
    application.add_handler(CommandHandler("cancel", on_text))
    application.add_handler(MessageHandler(filters.Document.ALL, on_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return application


def load_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in the environment; do not commit it.")
    return token


def main() -> None:
    create_application(load_token()).run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
