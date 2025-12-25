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
from ..models.delivery import DeliveryRecord


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
        # Check auto-save status
        auto_save = context.user_data.get("auto_save_enabled", False)
        auto_save_status = "🟢 ON" if auto_save else "🔴 OFF"

        keyboard = [
            [
                InlineKeyboardButton("📸 Upload Bukti", callback_data="menu_upload"),
                InlineKeyboardButton("📊 Cek Pengiriman", callback_data="menu_check")
            ],
            [
                InlineKeyboardButton("📈 Total Hari Ini", callback_data="menu_total"),
                InlineKeyboardButton("ℹ️ Bantuan", callback_data="menu_help")
            ],
            [
                InlineKeyboardButton(
                    f"⚡ Auto-Save: {auto_save_status}",
                    callback_data="toggle_autosave"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        auto_save_desc = (
            "_(Otomatis simpan tanpa konfirmasi)_"
            if auto_save
            else "_(Perlu konfirmasi sebelum simpan)_"
        )

        menu_message = f"""
🏠 *Menu Utama - Bot Tracking Pengiriman*

Pilih salah satu opsi di bawah ini atau gunakan perintah langsung:

📸 Upload Bukti Penimbangan
📊 Lihat 5 Pengiriman Terbaru
📈 Total Berat Bersih Hari Ini
ℹ️ Bantuan & Info

⚡ *Auto-Save:* {auto_save_status}
{auto_save_desc}

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
        """Handle delivery receipt photo uploads - automatically processes any image."""
        try:
            # Check if there's already pending data
            if context.user_data.get("pending_receipt"):
                await update.message.reply_text(
                    "⚠️ Anda masih memiliki pengiriman yang belum "
                    "disetujui!\n\n"
                    "Silakan setujui atau tolak pengiriman sebelumnya "
                    "terlebih dahulu, atau kirim foto ini lagi setelah "
                    "menyelesaikan yang sebelumnya."
                )
                return

            await update.message.reply_text(
                "📸 Bukti penimbangan diterima! Memproses... "
                "Ini mungkin memakan waktu beberapa detik."
            )

            # Get the highest quality photo
            photo = update.message.photo[-1]
            photo_file = await context.bot.get_file(photo.file_id)

            # Download image bytes
            image_bytes = await photo_file.download_as_bytearray()
            image_bytes = bytes(image_bytes)

            # Save to temp file for later upload to Drive
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name
            temp_file.close()

            logger.info(
                f"Processing delivery receipt for user {update.effective_user.id}"
            )

            # Extract receipt data and categorize material in parallel (async)
            # Run blocking Gemini calls in thread pool to avoid blocking event loop
            extraction_task = asyncio.to_thread(
                self.gemini_client.extract_receipt_data,
                image_bytes
            )

            # Start extraction first
            receipt_data, confidence = await extraction_task

            if receipt_data is None:
                await update.message.reply_text(
                    "❌ Maaf, saya tidak dapat mengekstrak data dari bukti ini. "
                    "Pastikan foto jelas dan coba lagi."
                )
                os.unlink(temp_file_path)  # Clean up temp file
                return

            # Check confidence threshold - reject low-quality extractions early
            if confidence < settings.min_confidence_threshold:
                await update.message.reply_text(
                    f"⚠️ *Kualitas ekstraksi terlalu rendah* ({confidence * 100:.0f}%)\n\n"
                    "Data yang diekstrak mungkin tidak akurat. "
                    "Silakan coba lagi dengan foto yang lebih jelas:\n\n"
                    "✅ Pastikan pencahayaan baik\n"
                    "✅ Fokus kamera tajam\n"
                    "✅ Seluruh teks terlihat jelas\n"
                    "✅ Tidak ada bayangan atau silau",
                    parse_mode="Markdown"
                )
                os.unlink(temp_file_path)  # Clean up temp file
                logger.warning(
                    f"Rejected extraction due to low confidence: {confidence:.2f} "
                    f"(threshold: {settings.min_confidence_threshold})"
                )
                return

            # Categorize the material (also run in thread pool)
            material_type = await asyncio.to_thread(
                self.gemini_client.categorize_material,
                receipt_data.material_name
            )

            # Check if auto-save mode is enabled
            auto_save_enabled = context.user_data.get("auto_save_enabled", False)

            if auto_save_enabled:
                # Auto-save mode: Save directly without confirmation
                await self._save_delivery_directly(
                    update,
                    context,
                    receipt_data,
                    material_type,
                    confidence,
                    temp_file_path
                )
                return

            # Store data in user context for approval
            context.user_data["pending_receipt"] = receipt_data
            context.user_data["pending_material_type"] = material_type
            context.user_data["pending_confidence"] = confidence
            context.user_data["pending_image_path"] = temp_file_path

            # Create inline keyboard for approval
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Setuju & Simpan",
                        callback_data="approve_delivery"
                    ),
                    InlineKeyboardButton(
                        "✏️ Edit Data",
                        callback_data="edit_delivery"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Tolak",
                        callback_data="reject_delivery"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send confirmation request
            confirmation = f"""
📋 *Silakan periksa data yang diekstrak:*

• *No Nota:* {receipt_data.receipt_number}
• *Waktu Timbang:* {receipt_data.weighing_datetime}
• *No Timbangan:* {receipt_data.scale_number}
• *No Kendaraan:* {receipt_data.vehicle_number}
• *Material:* {receipt_data.material_name}
• *Jenis:* {material_type}
• *Berat Isi:* {receipt_data.gross_weight} ton
• *Berat Kosong:* {receipt_data.empty_weight} ton
• *Berat Bersih:* {receipt_data.net_weight} ton
• *Confidence:* {confidence * 100:.0f}%

Apakah informasi ini benar?
            """
            await update.message.reply_text(
                confirmation.strip(),
                parse_mode="Markdown",
                reply_markup=reply_markup
            )

            logger.info(
                f"Awaiting approval for delivery: {receipt_data.receipt_number} "
                f"from user {update.effective_user.id}"
            )

        except Exception as e:
            logger.error(f"Error processing photo: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Terjadi kesalahan saat memproses bukti Anda. "
                "Silakan coba lagi atau hubungi dukungan."
            )
            # Clean up temp file if it exists
            if 'temp_file_path' in locals():
                try:
                    os.unlink(temp_file_path)
                except:
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
        elif query.data == "toggle_autosave":
            await self.toggle_autosave(update, context)
        # Delivery approval callbacks
        elif query.data == "approve_delivery":
            await self.approve_delivery(update, context)
        elif query.data == "reject_delivery":
            await self.reject_delivery(update, context)
        elif query.data == "edit_delivery":
            await self.edit_delivery(update, context)

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

    async def toggle_autosave(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Toggle auto-save mode."""
        current_status = context.user_data.get("auto_save_enabled", False)
        new_status = not current_status
        context.user_data["auto_save_enabled"] = new_status

        status_text = "🟢 AKTIF" if new_status else "🔴 NONAKTIF"
        mode_desc = (
            "Foto akan otomatis disimpan tanpa konfirmasi.\n"
            "Cocok untuk upload banyak foto sekaligus!"
            if new_status
            else "Setiap foto perlu konfirmasi sebelum disimpan.\n"
            "Mode yang lebih aman untuk memastikan data akurat."
        )

        await update.callback_query.message.reply_text(
            f"⚡ *Auto-Save Mode: {status_text}*\n\n{mode_desc}",
            parse_mode="Markdown"
        )

        logger.info(
            f"User {update.effective_user.id} toggled auto-save to {new_status}"
        )

    async def _save_delivery_directly(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        receipt_data,
        material_type: str,
        confidence: float,
        temp_image_path: str
    ):
        """Save delivery directly without user confirmation (auto-save mode)."""
        try:
            await update.message.reply_text(
                "💾 Auto-save: Menyimpan data pengiriman..."
            )

            # Upload image to Cloud Storage
            receipt_url = ""
            try:
                if temp_image_path and os.path.exists(temp_image_path):
                    receipt_url = await asyncio.to_thread(
                        self.sheets_client.upload_image_to_storage,
                        image_path=temp_image_path,
                        receipt_number=receipt_data.receipt_number,
                        weighing_datetime=receipt_data.weighing_datetime
                    )
                    logger.info(f"Image uploaded to Cloud Storage: {receipt_url}")
            except Exception as e:
                logger.error(f"Failed to upload to Cloud Storage: {e}")

            # Create delivery record
            delivery = DeliveryRecord.from_receipt_data(
                receipt=receipt_data,
                material_type=material_type,
                confidence=confidence,
                receipt_url=receipt_url,
                notes="Auto-saved"
            )

            # Save to Google Sheets
            success = await asyncio.to_thread(
                self.sheets_client.append_delivery,
                delivery
            )

            if success:
                success_message = f"""
✅ *Auto-saved!*

• *No Nota:* {receipt_data.receipt_number}
• *Material:* {receipt_data.material_name}
• *Berat Bersih:* {receipt_data.net_weight} ton
• *Kendaraan:* {receipt_data.vehicle_number}

Kirim foto lagi untuk upload berikutnya! 📸
                """
                await update.message.reply_text(
                    success_message.strip(),
                    parse_mode="Markdown"
                )
                logger.info(
                    f"Auto-saved delivery: {receipt_data.receipt_number} "
                    f"for user {update.effective_user.id}"
                )
            else:
                await update.message.reply_text(
                    "❌ Gagal menyimpan data. Silakan coba lagi."
                )

        except Exception as e:
            logger.error(f"Error in auto-save: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Terjadi kesalahan saat menyimpan data secara otomatis."
            )
        finally:
            # Clean up temp file
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.unlink(temp_image_path)
                    logger.info(f"Cleaned up temp file: {temp_image_path}")
                except Exception as e:
                    logger.error(f"Failed to delete temp file: {e}")

    async def approve_delivery(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Approve and save the delivery record."""
        try:
            receipt_data = context.user_data.get("pending_receipt")
            material_type = context.user_data.get("pending_material_type")
            confidence = context.user_data.get("pending_confidence")
            temp_image_path = context.user_data.get("pending_image_path")

            if not receipt_data:
                await update.callback_query.message.reply_text(
                    "❌ Data tidak ditemukan. Silakan upload ulang."
                )
                return

            await update.callback_query.message.reply_text(
                "💾 Menyimpan data pengiriman..."
            )

            # Upload image to Google Cloud Storage and save to Sheets in parallel
            # Run both blocking I/O operations concurrently
            receipt_url = ""

            async def upload_image():
                """Upload image to Cloud Storage."""
                try:
                    if temp_image_path and os.path.exists(temp_image_path):
                        url = await asyncio.to_thread(
                            self.sheets_client.upload_image_to_storage,
                            image_path=temp_image_path,
                            receipt_number=receipt_data.receipt_number,
                            weighing_datetime=receipt_data.weighing_datetime
                        )
                        logger.info(f"Image uploaded to Cloud Storage: {url}")
                        return url
                except Exception as e:
                    logger.error(f"Failed to upload to Cloud Storage: {e}")
                return ""

            # Start image upload first (can happen in background)
            receipt_url = await upload_image()

            # Create delivery record
            delivery = DeliveryRecord.from_receipt_data(
                receipt=receipt_data,
                material_type=material_type,
                confidence=confidence,
                receipt_url=receipt_url,
                notes=""
            )

            # Save to Google Sheets (run in thread pool)
            success = await asyncio.to_thread(
                self.sheets_client.append_delivery,
                delivery
            )

            if success:
                success_message = f"""
✅ *Pengiriman berhasil disimpan!*

• *No Nota:* {receipt_data.receipt_number}
• *Material:* {receipt_data.material_name}
• *Berat Bersih:* {receipt_data.net_weight} ton
• *Kendaraan:* {receipt_data.vehicle_number}

Data telah ditambahkan ke Google Sheets.
                """
                if receipt_url:
                    success_message += f"\n[Lihat Bukti]({receipt_url})"

                await update.callback_query.message.reply_text(
                    success_message.strip(),
                    parse_mode="Markdown"
                )

                logger.info(
                    f"Delivery saved: {receipt_data.receipt_number} "
                    f"for user {update.effective_user.id}"
                )
            else:
                await update.callback_query.message.reply_text(
                    "❌ Gagal menyimpan data. Silakan coba lagi."
                )

        except Exception as e:
            logger.error(f"Error approving delivery: {e}", exc_info=True)
            await update.callback_query.message.reply_text(
                "❌ Terjadi kesalahan saat menyimpan data."
            )
        finally:
            # Clean up temp file
            temp_image_path = context.user_data.get("pending_image_path")
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.unlink(temp_image_path)
                    logger.info(f"Cleaned up temp file: {temp_image_path}")
                except Exception as e:
                    logger.error(f"Failed to delete temp file: {e}")

            # Clear only pending data (not entire context) to allow multiple uploads
            context.user_data.pop("pending_receipt", None)
            context.user_data.pop("pending_material_type", None)
            context.user_data.pop("pending_confidence", None)
            context.user_data.pop("pending_image_path", None)
            context.user_data.pop("edit_mode", None)

    async def reject_delivery(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Reject the delivery record."""
        # Clean up temp file
        temp_image_path = context.user_data.get("pending_image_path")
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.unlink(temp_image_path)
            except:
                pass

        # Clear only pending data (not entire context) to allow multiple uploads
        context.user_data.pop("pending_receipt", None)
        context.user_data.pop("pending_material_type", None)
        context.user_data.pop("pending_confidence", None)
        context.user_data.pop("pending_image_path", None)
        context.user_data.pop("edit_mode", None)

        await update.callback_query.message.reply_text(
            "❌ Pengiriman dibatalkan. Kirim foto baru untuk upload lagi."
        )

    async def edit_delivery(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Start edit mode for delivery data."""
        receipt_data = context.user_data.get("pending_receipt")

        if not receipt_data:
            await update.callback_query.message.reply_text(
                "❌ Data tidak ditemukan. Silakan upload ulang."
            )
            return

        # Set edit mode flag
        context.user_data["edit_mode"] = True

        edit_message = """
✏️ *Mode Edit Data*

Silakan kirim data yang ingin diubah dalam format:

`field: nilai_baru`

*Field yang bisa diubah:*
• `no_nota` - Nomor nota
• `kendaraan` - Nomor kendaraan
• `material` - Nama material
• `berat_isi` - Berat isi (ton)
• `berat_kosong` - Berat kosong (ton)

*Contoh:*
`no_nota: 12345`
`material: Batu Split`
`berat_isi: 25.5`

Kirim `selesai` jika sudah selesai edit.
        """

        await update.callback_query.message.reply_text(
            edit_message.strip(),
            parse_mode="Markdown"
        )

    async def handle_text_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle text messages for editing data or custom date input."""
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

        # Handle edit mode
        if not context.user_data.get("edit_mode"):
            # Not in edit mode, reject text messages
            await update.message.reply_text(
                "📋 Silakan gunakan menu untuk berinteraksi dengan bot.\n\n"
                "Ketik /menu atau /start untuk melihat opsi yang tersedia."
            )
            return

        # Check if user is done editing
        if text.lower() == "selesai":
            context.user_data["edit_mode"] = False
            receipt_data = context.user_data.get("pending_receipt")

            # Show updated data with approval buttons
            material_type = context.user_data.get("pending_material_type")
            confidence = context.user_data.get("pending_confidence")

            # Recalculate net weight
            receipt_data.net_weight = receipt_data.gross_weight - receipt_data.empty_weight

            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Setuju & Simpan",
                        callback_data="approve_delivery"
                    ),
                    InlineKeyboardButton(
                        "✏️ Edit Lagi",
                        callback_data="edit_delivery"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Tolak",
                        callback_data="reject_delivery"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            confirmation = f"""
📋 *Data yang sudah diedit:*

• *No Nota:* {receipt_data.receipt_number}
• *Waktu Timbang:* {receipt_data.weighing_datetime}
• *No Timbangan:* {receipt_data.scale_number}
• *No Kendaraan:* {receipt_data.vehicle_number}
• *Material:* {receipt_data.material_name}
• *Jenis:* {material_type}
• *Berat Isi:* {receipt_data.gross_weight} ton
• *Berat Kosong:* {receipt_data.empty_weight} ton
• *Berat Bersih:* {receipt_data.net_weight} ton
• *Confidence:* {confidence * 100:.0f}%

Apakah informasi ini benar?
            """
            await update.message.reply_text(
                confirmation.strip(),
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            return

        # Parse edit command (format: "field: value")
        if ":" not in text:
            await update.message.reply_text(
                "❌ Format salah. Gunakan: `field: nilai`\nContoh: `no_nota: 12345`",
                parse_mode="Markdown"
            )
            return

        field, value = text.split(":", 1)
        field = field.strip().lower()
        value = value.strip()

        receipt_data = context.user_data.get("pending_receipt")

        try:
            if field == "no_nota":
                receipt_data.receipt_number = value
                await update.message.reply_text(f"✅ No Nota diubah menjadi: {value}")
            elif field == "kendaraan":
                receipt_data.vehicle_number = value
                await update.message.reply_text(f"✅ No Kendaraan diubah menjadi: {value}")
            elif field == "material":
                receipt_data.material_name = value
                # Re-categorize material
                material_type = self.gemini_client.categorize_material(value)
                context.user_data["pending_material_type"] = material_type
                await update.message.reply_text(
                    f"✅ Material diubah menjadi: {value}\n"
                    f"Kategori: {material_type}"
                )
            elif field == "berat_isi":
                receipt_data.gross_weight = float(value)
                receipt_data.net_weight = receipt_data.gross_weight - receipt_data.empty_weight
                await update.message.reply_text(
                    f"✅ Berat Isi diubah menjadi: {value} ton\n"
                    f"Berat Bersih: {receipt_data.net_weight} ton"
                )
            elif field == "berat_kosong":
                receipt_data.empty_weight = float(value)
                receipt_data.net_weight = receipt_data.gross_weight - receipt_data.empty_weight
                await update.message.reply_text(
                    f"✅ Berat Kosong diubah menjadi: {value} ton\n"
                    f"Berat Bersih: {receipt_data.net_weight} ton"
                )
            else:
                await update.message.reply_text(
                    f"❌ Field '{field}' tidak dikenal.\n"
                    f"Field yang tersedia: no_nota, kendaraan, material, berat_isi, berat_kosong"
                )
                return

            context.user_data["pending_receipt"] = receipt_data

        except ValueError:
            await update.message.reply_text(
                f"❌ Nilai tidak valid untuk {field}. Pastikan format benar."
            )
        except Exception as e:
            logger.error(f"Error editing field {field}: {e}")
            await update.message.reply_text(
                f"❌ Terjadi kesalahan saat mengubah {field}"
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
        application = Application.builder().token(self.bot_token).build()
        self.setup_handlers(application)
        logger.info("Telegram application created and configured")
        return application

    def run_polling(self):
        """Run the bot in polling mode (for development)."""
        application = self.create_application()

        logger.info("Starting bot in polling mode...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
