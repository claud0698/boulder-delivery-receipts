"""Telegram bot handler for delivery receipt tracking."""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from loguru import logger
import tempfile
import os

from ..config import settings
from ..llm.gemini_client import GeminiClient
from ..storage.sheets_client import SheetsClient
from ..models.delivery import DeliveryRecord, TokenUsageRecord


class TelegramHandler:
    """Handler for Telegram bot interactions - Delivery Receipt Tracking."""

    def __init__(self):
        """Initialize Telegram handler."""
        self.bot_token = settings.telegram_bot_token
        self.gemini_client = GeminiClient()
        self.sheets_client = SheetsClient()

        logger.info("Telegram handler initialized for delivery tracking")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_message = """
👋 Selamat datang di Bot Tracking Pengiriman Batu!

Saya dapat membantu Anda melacak pengiriman material secara otomatis menggunakan AI.

💡 *Cara tercepat:* Langsung kirim foto bukti penimbangan!
Saya akan otomatis memproses dan mengekstrak datanya.

Perintah yang tersedia:
/menu - Menu utama dengan tombol interaktif
/total - Lihat total berat bersih berdasarkan tanggal

Fitur yang tersedia:
📸 Upload Bukti Penimbangan
📊 Lihat Pengiriman Terbaru
📈 Total Berat Bersih
ℹ️ Bantuan & Info
        """

        # Add quick access menu buttons
        keyboard = [
            [
                InlineKeyboardButton("🚀 Mulai Sekarang", callback_data="menu_upload"),
                InlineKeyboardButton("📋 Lihat Menu", callback_data="show_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_message.strip(),
            reply_markup=reply_markup
        )

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command - show main menu with quick action buttons."""
        keyboard = [
            [
                InlineKeyboardButton("📸 Upload Bukti", callback_data="menu_upload"),
                InlineKeyboardButton("📊 Cek Pengiriman", callback_data="menu_check")
            ],
            [
                InlineKeyboardButton("📈 Total Hari Ini", callback_data="menu_total"),
                InlineKeyboardButton("ℹ️ Bantuan", callback_data="menu_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        menu_message = """
🏠 *Menu Utama - Bot Tracking Pengiriman*

Pilih salah satu opsi di bawah ini atau gunakan perintah langsung:

📸 Upload Bukti Penimbangan
📊 Lihat 5 Pengiriman Terbaru
📈 Total Berat Bersih Hari Ini
ℹ️ Bantuan & Info

Atau langsung kirim foto bukti penimbangan! 📷
        """
        await update.message.reply_text(
            menu_message.strip(),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command (called via menu button)."""
        help_message = """
📱 Cara menggunakan Bot Tracking Pengiriman:

*Perintah Tersedia:*
• **/menu** - Tampilkan menu utama dengan tombol interaktif
• **/total** - Pilih tanggal untuk melihat total berat bersih

*Fitur Utama:*
1. **📸 Upload Bukti Penimbangan**
   - Langsung kirim foto atau klik tombol Upload di menu
   - AI akan mengekstrak data secara otomatis
   - Mode Normal: Periksa dan setujui data sebelum disimpan
   - Mode Auto-Save: Otomatis simpan tanpa konfirmasi

2. **📊 Cek Pengiriman**
   - Lihat 5 pengiriman terbaru
   - Termasuk nomor nota, material, berat, dan tanggal

3. **📈 Total Berat Bersih**
   - Pilih tanggal (hari ini, kemarin, atau custom)
   - Lihat breakdown per material
   - Total berat bersih keseluruhan

4. **⚡ Auto-Save Mode**
   - Toggle ON/OFF di menu utama
   - ON: Otomatis simpan semua foto (upload batch cepat)
   - OFF: Konfirmasi setiap upload (lebih aman)

5. **✏️ Edit Data** (Mode Normal)
   - Setelah upload, Anda bisa edit data
   - Format: `field: nilai_baru`
   - Field: no_nota, kendaraan, material, berat_isi, berat_kosong

*Tips untuk hasil terbaik:*
✅ Pastikan foto jelas dan terang
✅ Sertakan seluruh bukti dalam foto
✅ Hindari bayangan atau silau
✅ Pastikan teks dapat dibaca dengan jelas
        """
        await update.message.reply_text(
            help_message.strip(),
            parse_mode="Markdown"
        )

    async def total_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /total command - show interactive date picker."""
        from datetime import datetime, timedelta

        today = datetime.now()
        yesterday = today - timedelta(days=1)
        day_before = today - timedelta(days=2)

        keyboard = [
            [
                InlineKeyboardButton(
                    f"📅 Hari Ini ({today.strftime('%d/%m')})",
                    callback_data=f"total_date:{today.strftime('%Y-%m-%d')}"
                )
            ],
            [
                InlineKeyboardButton(
                    f"📅 Kemarin ({yesterday.strftime('%d/%m')})",
                    callback_data=f"total_date:{yesterday.strftime('%Y-%m-%d')}"
                )
            ],
            [
                InlineKeyboardButton(
                    f"📅 {day_before.strftime('%d/%m/%Y')}",
                    callback_data=f"total_date:{day_before.strftime('%Y-%m-%d')}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📝 Pilih Tanggal Lain...",
                    callback_data="total_custom_date"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📊 *Total Berat Bersih Pengiriman*\n\n"
            "Pilih tanggal untuk melihat total:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    async def show_total_for_date(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        date_str: str
    ):
        """Show total berat bersih for a specific date."""
        try:
            from datetime import datetime

            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            display_date = date_obj.strftime("%d %B %Y")

            if update.callback_query:
                await update.callback_query.message.reply_text(
                    f"📊 Menghitung total berat untuk {display_date}..."
                )
                message_obj = update.callback_query.message
            else:
                await update.message.reply_text(
                    f"📊 Menghitung total berat untuk {display_date}..."
                )
                message_obj = update.message

            deliveries = self.sheets_client.get_deliveries_by_date(date_str)

            if not deliveries:
                await message_obj.reply_text(
                    f"📭 Tidak ada data pengiriman untuk {display_date}."
                )
                return

            total_berat = 0.0
            material_totals = {}

            for delivery in deliveries:
                berat_bersih = delivery.get("berat_bersih", "0")
                material = delivery.get("nama_material", "Unknown")

                try:
                    berat = float(berat_bersih)
                    total_berat += berat

                    if material not in material_totals:
                        material_totals[material] = 0.0
                    material_totals[material] += berat
                except (ValueError, TypeError):
                    pass

            message = f"📊 *Total Pengiriman - {display_date}*\n\n"
            message += f"📦 *Jumlah Pengiriman:* {len(deliveries)}\n\n"

            message += "*Breakdown per Material:*\n"
            for material, berat in sorted(
                material_totals.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                message += f"• {material}: {berat:.2f} ton\n"

            message += f"\n{'='*30}\n"
            message += f"*TOTAL BERAT BERSIH: {total_berat:.2f} ton*"

            await message_obj.reply_text(message, parse_mode="Markdown")

            logger.info(
                f"Sent total summary for {date_str} to user {update.effective_user.id}"
            )

        except Exception as e:
            logger.error(f"Error in show_total_for_date: {e}")
            message_obj = update.callback_query.message if update.callback_query else update.message
            await message_obj.reply_text(
                "❌ Maaf, terjadi kesalahan saat menghitung total."
            )

    async def check_delivery_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /cek_pengiriman command - show 5 latest deliveries."""
        try:
            await update.message.reply_text("📊 Mengambil data pengiriman terbaru...")

            # Get latest deliveries from sheets
            deliveries = self.sheets_client.get_latest_deliveries(limit=5)

            if not deliveries:
                await update.message.reply_text(
                    "Belum ada data pengiriman! Kirim foto bukti penimbangan untuk memulai."
                )
                return

            # Format deliveries for display
            message = "🚚 *5 Pengiriman Terbaru:*\n\n"

            for i, delivery in enumerate(deliveries, 1):
                no_nota = delivery.get("no_nota", "N/A")
                tanggal = delivery.get("tanggal", "N/A")
                waktu = delivery.get("waktu", "N/A")
                material = delivery.get("nama_material", "Unknown")
                berat_bersih = delivery.get("berat_bersih", "0")
                kendaraan = delivery.get("no_kendaraan", "N/A")
                status = delivery.get("status", "N/A")

                message += f"{i}. *{material}*\n"
                message += f"   📋 Nota: {no_nota}\n"
                message += f"   ⚖️ Berat: {berat_bersih} ton\n"
                message += f"   🚛 Kendaraan: {kendaraan}\n"
                message += f"   📅 {tanggal} {waktu}\n"
                message += f"   ✓ {status}\n\n"

            # Add total weight
            try:
                total_weight = sum(
                    float(d.get("berat_bersih", 0))
                    for d in deliveries
                    if d.get("berat_bersih")
                )
                message += f"─────────────\n"
                message += f"*Total Berat:* {total_weight:.2f} ton"
            except (ValueError, TypeError):
                pass

            await update.message.reply_text(message, parse_mode="Markdown")

            logger.info(f"Sent latest deliveries to user {update.effective_user.id}")

        except Exception as e:
            logger.error(f"Error in check_delivery_command: {e}")
            await update.message.reply_text(
                "❌ Maaf, terjadi kesalahan saat mengambil data pengiriman. "
                "Silakan coba lagi nanti."
            )

    async def upload_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /upload command - prompt for receipt image."""
        message = """
📸 Silakan kirim foto bukti penimbangan!

Pastikan:
✅ Seluruh bukti terlihat jelas
✅ Foto terang dan fokus
✅ Teks dapat dibaca

Saya akan mengekstrak detailnya dan menyimpan data pengiriman secara otomatis.
        """
        await update.message.reply_text(message.strip())

    async def handle_photo(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle delivery receipt photo uploads - single or media group."""
        try:
            # Acknowledge receipt immediately
            await update.message.reply_text(
                "📸 Foto diterima! Memproses..."
            )

            # Get the highest quality photo
            photo = update.message.photo[-1]
            photo_file = await context.bot.get_file(photo.file_id)

            # Download image bytes
            image_bytes = await photo_file.download_as_bytearray()
            image_bytes = bytes(image_bytes)

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name
            temp_file.close()

            logger.info(
                f"Processing image for user {update.effective_user.id}"
            )

            # Process single image in background
            asyncio.create_task(
                self._process_single_image(
                    chat_id=update.effective_chat.id,
                    temp_file_path=temp_file_path,
                    context=context
                )
            )

        except Exception as e:
            logger.error(f"Error handling photo: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Terjadi kesalahan saat menerima foto. "
                "Silakan coba lagi."
            )

    async def _process_single_image(
        self,
        chat_id: int,
        temp_file_path: str,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Process single image: upload to GCS, extract data, save to Sheets."""
        try:
            logger.info(f"Processing single image for chat {chat_id}")

            # Step 1: Upload to GCS first to get URI
            import time
            temp_receipt_id = f"temp_{int(time.time())}_{chat_id}"
            temp_datetime = time.strftime("%Y-%m-%d %H:%M:%S")

            receipt_url, gcs_uri = await asyncio.to_thread(
                self.sheets_client.upload_image_to_storage,
                image_path=temp_file_path,
                receipt_number=temp_receipt_id,
                weighing_datetime=temp_datetime
            )
            logger.info(f"Image uploaded to GCS: {gcs_uri}")

            # Step 2: Extract receipt data using GCS URI
            receipt_data, confidence, token_usage = await asyncio.to_thread(
                self.gemini_client.extract_receipt_data,
                gcs_uri=gcs_uri
            )

            # Log token usage
            if token_usage:
                logger.info(
                    f"Token usage: {token_usage.get('total_token_count', 0)} "
                    f"tokens (prompt: {token_usage.get('prompt_token_count', 0)}, "
                    f"output: {token_usage.get('candidates_token_count', 0)})"
                )

            if receipt_data is None:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Tidak dapat mengekstrak data dari bukti. "
                    "Pastikan foto jelas."
                )
                os.unlink(temp_file_path)
                return

            # Log token usage to Sheets (non-blocking)
            if token_usage:
                try:
                    token_record = TokenUsageRecord(
                        receipt_number=receipt_data.receipt_number,
                        operation="extraction",
                        model="gemini-2.5-flash-lite",
                        prompt_tokens=token_usage.get('prompt_token_count', 0),
                        output_tokens=token_usage.get(
                            'candidates_token_count', 0
                        ),
                        total_tokens=token_usage.get('total_token_count', 0)
                    )
                    asyncio.create_task(
                        asyncio.to_thread(
                            self.sheets_client.append_token_usage,
                            token_record
                        )
                    )
                except Exception as e:
                    logger.warning(f"Token usage logging failed: {e}")

            # Step 3: Create delivery record (material_type now in receipt_data)
            delivery = DeliveryRecord.from_receipt_data(
                receipt=receipt_data,
                confidence=confidence,
                receipt_url=receipt_url,
                notes=""
            )
            logger.info(f"Material categorized as: {delivery.material_type}")

            # Step 4: Save to Google Sheets
            success = await asyncio.to_thread(
                self.sheets_client.append_delivery,
                delivery
            )

            # Clean up temp file
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass

            # Step 5: Notify user
            if success:
                message = f"""
✅ *Tersimpan!*

• *No Nota:* {receipt_data.receipt_number}
• *Material:* {receipt_data.material_name}
• *Berat Bersih:* {receipt_data.net_weight} ton
• *Kendaraan:* {receipt_data.vehicle_number}

Data sudah masuk ke Google Sheets.
                """
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message.strip(),
                    parse_mode="Markdown"
                )
                logger.info(
                    f"Saved delivery: {receipt_data.receipt_number}"
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Gagal menyimpan ke Google Sheets. "
                    "Silakan coba lagi."
                )

        except Exception as e:
            logger.error(f"Error processing single image: {e}", exc_info=True)
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Terjadi kesalahan saat memproses. "
                    "Silakan coba lagi."
                )
            except Exception:
                pass
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass

    async def _process_multiple_images(
        self,
        chat_id: int,
        temp_file_paths: list[str],
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Process multiple images: batch upload to GCS, extract, save."""
        try:
            import time
            logger.info(
                f"Processing {len(temp_file_paths)} images for chat {chat_id}"
            )

            # Step 1: Prepare data for batch upload
            temp_datetime = time.strftime("%Y-%m-%d %H:%M:%S")
            receipt_numbers = [
                f"temp_{int(time.time())}_{chat_id}_{i}"
                for i in range(len(temp_file_paths))
            ]
            weighing_datetimes = [temp_datetime] * len(temp_file_paths)

            # Step 2: Upload all images to GCS concurrently
            upload_results = await asyncio.to_thread(
                self.sheets_client.batch_upload_images_to_storage,
                image_paths=temp_file_paths,
                receipt_numbers=receipt_numbers,
                weighing_datetimes=weighing_datetimes
            )
            logger.info(f"Batch uploaded {len(upload_results)} images to GCS")

            # Step 3: Process each image sequentially with Gemini
            deliveries = []
            successful_count = 0
            total_weight = 0.0

            for i, (temp_file_path, (receipt_url, gcs_uri)) in enumerate(
                zip(temp_file_paths, upload_results)
            ):
                try:
                    # Extract receipt data using GCS URI
                    receipt_data, confidence, token_usage = (
                        await asyncio.to_thread(
                            self.gemini_client.extract_receipt_data,
                            gcs_uri=gcs_uri
                        )
                    )

                    if receipt_data is None:
                        logger.warning(f"Failed to extract data from image {i+1}")
                        continue

                    # Log token usage (non-blocking)
                    if token_usage:
                        try:
                            token_record = TokenUsageRecord(
                                receipt_number=receipt_data.receipt_number,
                                operation="extraction",
                                model="gemini-2.5-flash-lite",
                                prompt_tokens=token_usage.get(
                                    'prompt_token_count', 0
                                ),
                                output_tokens=token_usage.get(
                                    'candidates_token_count', 0
                                ),
                                total_tokens=token_usage.get(
                                    'total_token_count', 0
                                )
                            )
                            asyncio.create_task(
                                asyncio.to_thread(
                                    self.sheets_client.append_token_usage,
                                    token_record
                                )
                            )
                        except Exception as e:
                            logger.warning(f"Token usage logging failed: {e}")

                    # Create delivery record (material_type now in receipt_data)
                    delivery = DeliveryRecord.from_receipt_data(
                        receipt=receipt_data,
                        confidence=confidence,
                        receipt_url=receipt_url,
                        notes=""
                    )
                    deliveries.append(delivery)
                    successful_count += 1
                    total_weight += receipt_data.net_weight

                    logger.info(
                        f"Processed image {i+1}/{len(temp_file_paths)}: "
                        f"{receipt_data.receipt_number}"
                    )

                except Exception as e:
                    logger.error(f"Error processing image {i+1}: {e}")
                    continue

            # Step 4: Batch save all deliveries to Sheets
            if deliveries:
                success = await asyncio.to_thread(
                    self.sheets_client.batch_append_deliveries,
                    deliveries
                )
            else:
                success = False

            # Clean up temp files
            for temp_file_path in temp_file_paths:
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

            # Step 5: Send summary message
            if success and deliveries:
                summary_lines = []
                for delivery in deliveries:
                    summary_lines.append(
                        f"• {delivery.receipt_number}: "
                        f"{delivery.net_weight}t"
                    )

                message = f"""
✅ *{successful_count} Pengiriman Tersimpan!*

{chr(10).join(summary_lines)}

*Total Berat Bersih:* {total_weight:.2f} ton

Data sudah masuk ke Google Sheets.
                """
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message.strip(),
                    parse_mode="Markdown"
                )
                logger.info(
                    f"Saved {successful_count} deliveries from batch"
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Gagal memproses {len(temp_file_paths)} foto. "
                    "Silakan coba lagi."
                )

        except Exception as e:
            logger.error(
                f"Error processing multiple images: {e}", exc_info=True
            )
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Terjadi kesalahan saat memproses foto. "
                    "Silakan coba lagi."
                )
            except Exception:
                pass
            # Clean up temp files
            for temp_file_path in temp_file_paths:
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle inline keyboard callbacks."""
        query = update.callback_query
        await query.answer()

        # Total date selection callbacks
        if query.data.startswith("total_date:"):
            date_str = query.data.split(":")[1]
            await self.show_total_for_date(update, context, date_str)
        elif query.data == "total_custom_date":
            await query.message.reply_text(
                "📝 *Masukkan tanggal yang ingin dilihat:*\n\n"
                "Format: `YYYY-MM-DD` atau `DD-MM-YYYY`\n"
                "Contoh: `2024-12-25` atau `25-12-2024`",
                parse_mode="Markdown"
            )
            context.user_data["awaiting_custom_date"] = True
        # Menu button callbacks
        elif query.data == "show_menu":
            await self.show_menu_inline(update, context)
        elif query.data == "menu_upload":
            await self.menu_upload_action(update, context)
        elif query.data == "menu_check":
            await self.menu_check_action(update, context)
        elif query.data == "menu_total":
            await self.menu_total_action(update, context)
        elif query.data == "menu_help":
            await self.menu_help_action(update, context)

    async def show_menu_inline(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Show menu via inline callback."""
        keyboard = [
            [
                InlineKeyboardButton("📸 Upload Bukti", callback_data="menu_upload"),
                InlineKeyboardButton("📊 Cek Pengiriman", callback_data="menu_check")
            ],
            [
                InlineKeyboardButton("📈 Total Hari Ini", callback_data="menu_total"),
                InlineKeyboardButton("ℹ️ Bantuan", callback_data="menu_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        menu_message = """
🏠 *Menu Utama - Bot Tracking Pengiriman*

Pilih salah satu opsi di bawah ini atau gunakan perintah langsung:

📸 Upload Bukti Penimbangan
📊 Lihat 5 Pengiriman Terbaru
📈 Total Berat Bersih Hari Ini
ℹ️ Bantuan & Info

Atau langsung kirim foto bukti penimbangan! 📷
        """
        await update.callback_query.message.reply_text(
            menu_message.strip(),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    async def menu_upload_action(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle upload action from menu button."""
        message = """
📸 Silakan kirim foto bukti penimbangan!

Pastikan:
✅ Seluruh bukti terlihat jelas
✅ Foto terang dan fokus
✅ Teks dapat dibaca

Saya akan mengekstrak detailnya dan menyimpan data pengiriman secara otomatis.
        """
        await update.callback_query.message.reply_text(message.strip())

    async def menu_check_action(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle check deliveries action from menu button."""
        try:
            await update.callback_query.message.reply_text(
                "📊 Mengambil data pengiriman terbaru..."
            )

            deliveries = self.sheets_client.get_latest_deliveries(limit=5)

            if not deliveries:
                await update.callback_query.message.reply_text(
                    "Belum ada data pengiriman! Kirim foto bukti penimbangan untuk memulai."
                )
                return

            message = "🚚 *5 Pengiriman Terbaru:*\n\n"

            for i, delivery in enumerate(deliveries, 1):
                no_nota = delivery.get("no_nota", "N/A")
                tanggal = delivery.get("tanggal", "N/A")
                waktu = delivery.get("waktu", "N/A")
                material = delivery.get("nama_material", "Unknown")
                berat_bersih = delivery.get("berat_bersih", "0")
                kendaraan = delivery.get("no_kendaraan", "N/A")
                status = delivery.get("status", "N/A")

                message += f"{i}. *{material}*\n"
                message += f"   📋 Nota: {no_nota}\n"
                message += f"   ⚖️ Berat: {berat_bersih} ton\n"
                message += f"   🚛 Kendaraan: {kendaraan}\n"
                message += f"   📅 {tanggal} {waktu}\n"
                message += f"   ✓ {status}\n\n"

            try:
                total_weight = sum(
                    float(d.get("berat_bersih", 0))
                    for d in deliveries
                    if d.get("berat_bersih")
                )
                message += f"─────────────\n"
                message += f"*Total Berat:* {total_weight:.2f} ton"
            except (ValueError, TypeError):
                pass

            await update.callback_query.message.reply_text(
                message,
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Error in menu_check_action: {e}")
            await update.callback_query.message.reply_text(
                "❌ Maaf, terjadi kesalahan saat mengambil data pengiriman."
            )

    async def menu_total_action(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle total today action from menu button."""
        try:
            from datetime import datetime

            date_obj = datetime.now()
            date_str = date_obj.strftime("%Y-%m-%d")
            display_date = "Hari Ini (" + date_obj.strftime("%d %B %Y") + ")"

            await update.callback_query.message.reply_text(
                f"📊 Menghitung total berat untuk {display_date}..."
            )

            deliveries = self.sheets_client.get_deliveries_by_date(date_str)

            if not deliveries:
                await update.callback_query.message.reply_text(
                    f"📭 Tidak ada data pengiriman untuk {display_date}."
                )
                return

            total_berat = 0.0
            material_totals = {}

            for delivery in deliveries:
                berat_bersih = delivery.get("berat_bersih", "0")
                material = delivery.get("nama_material", "Unknown")

                try:
                    berat = float(berat_bersih)
                    total_berat += berat

                    if material not in material_totals:
                        material_totals[material] = 0.0
                    material_totals[material] += berat
                except (ValueError, TypeError):
                    pass

            message = f"📊 *Total Pengiriman - {display_date}*\n\n"
            message += f"📦 *Jumlah Pengiriman:* {len(deliveries)}\n\n"

            message += "*Breakdown per Material:*\n"
            for material, berat in sorted(
                material_totals.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                message += f"• {material}: {berat:.2f} ton\n"

            message += f"\n{'='*30}\n"
            message += f"*TOTAL BERAT BERSIH: {total_berat:.2f} ton*"

            await update.callback_query.message.reply_text(
                message,
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Error in menu_total_action: {e}")
            await update.callback_query.message.reply_text(
                "❌ Maaf, terjadi kesalahan saat menghitung total."
            )

    async def menu_help_action(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle help action from menu button."""
        help_message = """
📱 Cara menggunakan Bot Tracking Pengiriman:

*Perintah Tersedia:*
• **/menu** - Tampilkan menu utama dengan tombol interaktif
• **/total** - Pilih tanggal untuk melihat total berat bersih

*Fitur Menu (gunakan tombol):*
1. **📸 Upload Bukti Penimbangan**
   - Langsung kirim foto atau klik tombol Upload di menu
   - AI akan mengekstrak data secara otomatis
   - Mode Normal: Periksa dan setujui data sebelum disimpan
   - Mode Auto-Save: Otomatis simpan tanpa konfirmasi

2. **📊 Cek Pengiriman**
   - Lihat 5 pengiriman terbaru
   - Termasuk nomor nota, material, berat, dan tanggal

3. **📈 Total Berat Bersih**
   - Pilih tanggal (hari ini, kemarin, atau custom)
   - Lihat breakdown per material
   - Total berat bersih keseluruhan

4. **⚡ Auto-Save Mode**
   - Toggle ON/OFF di menu utama
   - ON: Otomatis simpan semua foto (upload batch cepat)
   - OFF: Konfirmasi setiap upload (lebih aman)

5. **✏️ Edit Data** (Mode Normal)
   - Setelah upload, Anda bisa edit data
   - Format: `field: nilai_baru`
   - Field: no_nota, kendaraan, material, berat_isi, berat_kosong

*Tips untuk hasil terbaik:*
✅ Pastikan foto jelas dan terang
✅ Sertakan seluruh bukti dalam foto
✅ Hindari bayangan atau silau
✅ Pastikan teks dapat dibaca dengan jelas
        """
        await update.callback_query.message.reply_text(
            help_message.strip(),
            parse_mode="Markdown"
        )

    async def handle_text_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle text messages for custom date input."""
        text = update.message.text.strip()

        # Handle custom date input for /total
        if context.user_data.get("awaiting_custom_date"):
            context.user_data.pop("awaiting_custom_date", None)

            from datetime import datetime
            try:
                # Try parsing different formats
                try:
                    date_obj = datetime.strptime(text, "%Y-%m-%d")
                except ValueError:
                    date_obj = datetime.strptime(text, "%d-%m-%Y")

                date_str = date_obj.strftime("%Y-%m-%d")
                await self.show_total_for_date(update, context, date_str)
                return
            except ValueError:
                await update.message.reply_text(
                    "❌ Format tanggal salah. Gunakan:\n"
                    "`YYYY-MM-DD` atau `DD-MM-YYYY`\n\n"
                    "Contoh: `2024-12-25` atau `25-12-2024`",
                    parse_mode="Markdown"
                )
                return

        # For other text messages, guide user to menu
        await update.message.reply_text(
            "📋 Silakan gunakan menu untuk berinteraksi dengan bot.\n\n"
            "Ketik /menu atau /start untuk melihat opsi yang tersedia."
        )

    def setup_handlers(self, application: Application):
        """Set up all command and message handlers."""
        # Command handlers - only /start, /menu, and /total allowed
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("menu", self.menu_command))
        application.add_handler(CommandHandler("total", self.total_command))

        # Text message handler (only for editing data in edit mode)
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_text_message
            )
        )

        # Photo handler (only when awaiting receipt or in upload mode)
        application.add_handler(
            MessageHandler(filters.PHOTO, self.handle_photo)
        )

        # Callback handler for inline buttons
        application.add_handler(CallbackQueryHandler(self.handle_callback))

        logger.info("All handlers registered (menu-only mode)")

    def create_application(self) -> Application:
        """Create and configure the Telegram Application instance.

        Returns:
            Application: Configured Telegram application with all handlers registered.
        """
        from telegram.request import HTTPXRequest

        # Create custom request with longer timeouts for Cloud Run
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=30.0,  # 30 seconds for connection
            read_timeout=120.0,    # 2 minutes for read (handles slow networks)
            write_timeout=30.0,    # 30 seconds for write
            pool_timeout=10.0      # 10 seconds for getting connection from pool
        )

        application = (
            Application.builder()
            .token(self.bot_token)
            .request(request)
            .build()
        )
        self.setup_handlers(application)
        logger.info("Telegram application created with extended timeouts")
        return application

    def run_polling(self):
        """Run the bot in polling mode (for development)."""
        application = self.create_application()

        logger.info("Starting bot in polling mode...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
