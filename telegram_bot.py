import logging
import subprocess
import asyncio
import random
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from typing import Dict, List

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = 'your bot token'#bot farher

# Global state storage
user_states: Dict[int, dict] = {}
chat_histories: Dict[int, List[dict]] = {}
active_scenarios: Dict[int, dict] = {}

# Enhanced default user settings
DEFAULT_SETTINGS = {
    'response_length': 'medium',     # short, medium, long
    'story_length': 'medium',        # short, medium, long
    'detail_level': 'medium',        # basic, medium, detailed
    'math_precision': 2,             # decimal places for math calculations
    'language': 'uk',                # uk, ru, en
    'math_mode': 'calculator'        # calculator, problems
}

MAIN_MENU_KEYBOARD = [
    [KeyboardButton("💭 Звичайний режим")],
    [KeyboardButton("❤️ Романтичні пригоди"), KeyboardButton("🎭 Рольові пригоди")],
    [KeyboardButton("📖 Створення історій"), KeyboardButton("🔢 Математика")],
    [KeyboardButton("⚙️ Налаштування"), KeyboardButton("🗑 Очистити історію")]
]

class AIChat:
    @staticmethod
    async def get_ai_response(message: str, settings: dict, mode: str = 'chat') -> dict:
        """Gets optimized AI response based on settings and mode."""
        length_map = {
            'short': 50,
            'medium': 150,
            'long': 300
        }
        
        system_prompts = {
            'chat': """Ти - дружній та корисний асистент. Спілкуйся природно, 
                      проявляй емпатію та розуміння. Надавай корисні поради та інформацію.""",
            'romance': """Ти - автор романтичних історій. Створюй емоційні, 
                         захоплюючі сюжети про кохання та стосунки. Уникай 
                         недоречного контенту.""",
            'roleplay': """Ти - ведучий рольової гри. Створюй захоплюючі 
                          пригодницькі сценарії з чіткими варіантами вибору. 
                          Реагуй на дії гравця.""",
            'story': """Ти - креативний автор. Створюй цікаві історії базуючись 
                       на вказівках користувача. Додавай деталі та розвивай сюжет.""",
            'math_problems': """Ти - викладач математики. Створюй зрозумілі 
                              математичні задачі відповідного рівня складності."""
        }

        length_limit = length_map[settings['response_length']]
        system_prompt = system_prompts.get(mode, system_prompts['chat'])
        
        base_prompt = f"""System: {system_prompt}
Обмеження довжини: {length_limit} слів.
Рівень деталізації: {settings['detail_level']}
Мова відповіді: {settings['language']}

User: {message}"""

        try:
            process = subprocess.Popen(
                ['ollama', 'run', 'gemma2:9b'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            result, _ = process.communicate(input=base_prompt.encode(), timeout=300)
            response = result.decode().strip()
            
            choices = []
            if mode in ['romance', 'roleplay', 'story']:
                choices = await AIChat.generate_choices(response, settings)
                choices.append("🔙 Повернутись до головного меню")
            
            return {
                'text': response,
                'choices': choices
            }
        except Exception as e:
            logger.error(f"AI Response Error: {e}")
            return {
                'text': "Вибачте, виникла помилка. Спробуйте ще раз.",
                'choices': ["🔙 Повернутись до головного меню"]
            }

    @staticmethod
    async def generate_choices(response: str, settings: dict) -> List[str]:
        """Generates 2-4 continuation choices for interactive modes."""
        choice_prompt = f"""На основі цієї історії:
{response}
Створи 3-4 цікавих варіанти продовження. Зроби їх різноманітними та захоплюючими."""
        
        try:
            process = subprocess.Popen(
                ['ollama', 'run', 'gemma2:9b'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            result, _ = process.communicate(input=choice_prompt.encode(), timeout=300)
            choices = result.decode().strip().split('\n')
            valid_choices = [c.strip() for c in choices if c.strip()][:3]  # Limit to 3 choices
            return valid_choices
        except Exception:
            return ["Продовжити історію", "Почати заново", "🔙 Повернутись до головного меню"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initial menu."""
    user_id = update.effective_user.id
    if user_id not in user_states:
        user_states[user_id] = {'settings': DEFAULT_SETTINGS.copy()}
    
    reply_markup = ReplyKeyboardMarkup(MAIN_MENU_KEYBOARD, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 Вітаю! Виберіть режим:\n\n"
        "💭 Звичайний режим - спілкування з ШІ\n"
        "❤️ Романтичні пригоди - унікальні історії про кохання\n"
        "🎭 Рольові пригоди - різноманітні пригодницькі сценарії\n"
        "📖 Створення історій - генерація історій за вашим описом\n"
        "🔢 Математика - розв'язання задач та обчислення\n"
        "⚙️ Налаштування - персоналізація бота",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text messages."""
    message_text = update.message.text
    user_id = update.effective_user.id
    
    if user_id not in user_states:
        user_states[user_id] = {'settings': DEFAULT_SETTINGS.copy()}
    
    settings = user_states[user_id].get('settings', DEFAULT_SETTINGS.copy())
    
    # Handle return to main menu
    if message_text == "🔙 Повернутись до головного меню":
        reply_markup = ReplyKeyboardMarkup(MAIN_MENU_KEYBOARD, resize_keyboard=True)
        await update.message.reply_text("Головне меню:", reply_markup=reply_markup)
        user_states[user_id]['mode'] = None
        return

    mode_map = {
        "💭 Звичайний режим": ('chat', "Вибрано звичайний режим спілкування. Можете почати діалог!"),
        "❤️ Романтичні пригоди": ('romance', "Опишіть початкову ситуацію для романтичної історії:"),
        "🎭 Рольові пригоди": ('roleplay', "Опишіть свого персонажа та початкову ситуацію:"),
        "📖 Створення історій": ('story', "Опишіть, яку історію ви хочете отримати:"),
        "🔢 Математика": ('math', "Виберіть режим математики:\n1. Калькулятор\n2. Генерація задач"),
        "⚙️ Налаштування": ('settings', None),
        "🗑 Очистити історію": ('clear', None)
    }

    if message_text in mode_map:
        mode, response_text = mode_map[message_text]
        if mode == 'settings':
            await settings_menu(update, context)
            return
        elif mode == 'clear':
            chat_histories[user_id] = {}
            await update.message.reply_text("Історію очищено!")
            return
        
        user_states[user_id]['mode'] = mode
        if response_text:
            keyboard = [[KeyboardButton("🔙 Повернутись до головного меню")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(response_text, reply_markup=reply_markup)
    else:
        mode = user_states[user_id].get('mode', 'chat')
        
        if mode == 'math':
            result = await MathProcessor.process_math(message_text, settings)
            keyboard = [[KeyboardButton("🔙 Повернутись до головного меню")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(result['text'], reply_markup=reply_markup)
        else:
            response = await AIChat.get_ai_response(message_text, settings, mode)
            await update.message.reply_text(response['text'])
            
            if response['choices']:
                keyboard = [[KeyboardButton(choice)] for choice in response['choices']]
                keyboard.append([KeyboardButton("🔙 Повернутись до головного меню")])
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text("Виберіть варіант продовження:", reply_markup=reply_markup)

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows settings menu."""
    query = update.callback_query
    user_id = update.effective_user.id if update.effective_user else query.from_user.id
    
    if user_id not in user_states:
        user_states[user_id] = {'settings': DEFAULT_SETTINGS.copy()}
    
    settings = user_states[user_id].get('settings', DEFAULT_SETTINGS.copy())
    
    keyboard = [
        [InlineKeyboardButton("📏 Довжина відповіді", callback_data="settings_length")],
        [InlineKeyboardButton("📚 Довжина історій", callback_data="settings_story_length")],
        [InlineKeyboardButton("🔍 Рівень деталізації", callback_data="settings_detail")],
        [InlineKeyboardButton("🔢 Точність математики", callback_data="settings_math")],
        [InlineKeyboardButton("🧮 Режим математики", callback_data="settings_math_mode")],
        [InlineKeyboardButton("🌍 Мова", callback_data="settings_language")],
        [InlineKeyboardButton("↩️ До головного меню", callback_data="settings_back")]
    ]
    
    language_display = {
        'uk': 'Українська',
        'ru': 'Російська',
        'en': 'English'
    }
    
    current_settings = (
        f"Поточні налаштування:\n"
        f"📏 Довжина відповіді: {settings['response_length']}\n"
        f"📚 Довжина історій: {settings['story_length']}\n"
        f"🔍 Деталізація: {settings['detail_level']}\n"
        f"🔢 Точність математики: {settings['math_precision']}\n"
        f"🧮 Режим математики: {settings['math_mode']}\n"
        f"🌍 Мова: {language_display[settings['language']]}"
    )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.message.edit_text(current_settings, reply_markup=reply_markup)
    else:
        await update.message.reply_text(current_settings, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback queries from inline keyboards."""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in user_states:
        user_states[user_id] = {'settings': DEFAULT_SETTINGS.copy()}
    
    settings = user_states[user_id].get('settings', DEFAULT_SETTINGS.copy())

    # Define settings options
    setting_options = {
        'settings_length': {
            'title': "Виберіть довжину відповіді:",
            'options': [
                ('Коротка', 'short'),
                ('Середня', 'medium'),
                ('Довга', 'long')
            ],
            'setting_key': 'response_length'
        },
        'settings_story_length': {
            'title': "Виберіть довжину історій:",
            'options': [
                ('Коротка', 'short'),
                ('Середня', 'medium'),
                ('Довга', 'long')
            ],
            'setting_key': 'story_length'
        },
        'settings_detail': {
            'title': "Виберіть рівень деталізації:",
            'options': [
                ('Базовий', 'basic'),
                ('Середній', 'medium'),
                ('Детальний', 'detailed')
            ],
            'setting_key': 'detail_level'
        },
        'settings_math': {
            'title': "Виберіть точність обчислень:",
            'options': [
                ('0 знаків', 0),
                ('2 знаки', 2),
                ('4 знаки', 4)
            ],
            'setting_key': 'math_precision'
        },
        'settings_math_mode': {
            'title': "Виберіть режим математики:",
            'options': [
                ('Калькулятор', 'calculator'),
                ('Задачі', 'problems')
            ],
            'setting_key': 'math_mode'
        },
        'settings_language': {
            'title': "Виберіть мову:",
            'options': [
                ('Українська', 'uk'),
                ('Русский', 'ru'),
                ('English', 'en')
            ],
            'setting_key': 'language'
        }
    }

    # Handle setting value selection
    if query.data.startswith('set_'):
        _, setting_type, value = query.data.split('_')
        setting_key = None
        
        # Find the corresponding setting key
        for opt_key, opt_data in setting_options.items():
            if opt_key.endswith(setting_type):
                setting_key = opt_data['setting_key']
                break
        
        if setting_key:
            # Convert to proper type for numeric values
            if setting_key == 'math_precision':
                value = int(value)
            
            settings[setting_key] = value
            user_states[user_id]['settings'] = settings
            
            # Show confirmation
            await query.answer(f"Налаштування оновлено!")
            
            # Return to settings menu
            await show_settings_menu(query.message, user_id)
        return

    # Handle back button
    if query.data == 'settings_back':
        keyboard = [
            [KeyboardButton("💭 Звичайний режим")],
            [KeyboardButton("❤️ Романтичні пригоди"), KeyboardButton("🎭 Рольові пригоди")],
            [KeyboardButton("📖 Створення історій"), KeyboardButton("🔢 Математика")],
            [KeyboardButton("⚙️ Налаштування"), KeyboardButton("🗑 Очистити історію")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await query.message.edit_text("Оберіть опцію:", reply_markup=reply_markup)
        return

    # Handle return to main menu
    if query.data == 'return_main_menu':
        keyboard = [
            [KeyboardButton("💭 Звичайний режим")],
            [KeyboardButton("❤️ Романтичні пригоди"), KeyboardButton("🎭 Рольові пригоди")],
            [KeyboardButton("📖 Створення історій"), KeyboardButton("🔢 Математика")],
            [KeyboardButton("⚙️ Налаштування"), KeyboardButton("🗑 Очистити історію")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        if query.message:
            await query.message.edit_text("Головне меню:", reply_markup=reply_markup)
        return

    # Show options for selected setting
    if query.data in setting_options:
        option_data = setting_options[query.data]
        keyboard = [
            [InlineKeyboardButton(text, callback_data=f"set_{query.data.split('_')[1]}_{value}")]
            for text, value in option_data['options']
        ]
        keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="settings_back")])
        keyboard.append([InlineKeyboardButton("🏠 Головне меню", callback_data="return_main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        current_value = settings[option_data['setting_key']]
        
        await query.message.edit_text(
            f"{option_data['title']}\n"
            f"Поточне значення: {current_value}",
            reply_markup=reply_markup
        )

async def show_settings_menu(message, user_id: int) -> None:
    """Helper function to show settings menu."""
    settings = user_states[user_id].get('settings', DEFAULT_SETTINGS.copy())
    
    keyboard = [
        [InlineKeyboardButton("📏 Довжина відповіді", callback_data="settings_length")],
        [InlineKeyboardButton("📚 Довжина історій", callback_data="settings_story_length")],
        [InlineKeyboardButton("🔍 Рівень деталізації", callback_data="settings_detail")],
        [InlineKeyboardButton("🔢 Точність математики", callback_data="settings_math")],
        [InlineKeyboardButton("🧮 Режим математики", callback_data="settings_math_mode")],
        [InlineKeyboardButton("🌍 Мова", callback_data="settings_language")],
        [InlineKeyboardButton("🏠 Головне меню", callback_data="return_main_menu")]
    ]
    
    language_display = {
        'uk': 'Українська',
        'ru': 'Російська',
        'en': 'English'
    }
    
    current_settings = (
        f"Поточні налаштування:\n"
        f"📏 Довжина відповіді: {settings['response_length']}\n"
        f"📚 Довжина історій: {settings['story_length']}\n"
        f"🔍 Деталізація: {settings['detail_level']}\n"
        f"🔢 Точність математики: {settings['math_precision']}\n"
        f"🧮 Режим математики: {settings['math_mode']}\n"
        f"🌍 Мова: {language_display[settings['language']]}"
    )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.edit_text(current_settings, reply_markup=reply_markup)
    class MathProcessor:
        @staticmethod
        async def process_math(message: str, settings: dict) -> dict:
            """Process math input based on mode."""
            mode = settings['math_mode']
            precision = settings['math_precision']
            
            if mode == 'calculator':
                try:
                    # Basic sanitization and evaluation
                    expression = re.sub(r'[^0-9+\-*/().\s]', '', message)
                    result = eval(expression)
                    return {
                        'text': f"Результат: {round(result, precision)}"
                    }
                except:
                    return {
                        'text': "Помилка у виразі. Спробуйте ще раз."
                    }
            else:  # problems mode
                return await AIChat.get_ai_response(message, settings, 'math_problems')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    
    try:
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "Виникла помилка. Повертаюсь до головного меню...",
                reply_markup=ReplyKeyboardMarkup(MAIN_MENU_KEYBOARD, resize_keyboard=True)
            )
        elif update.message:
            await update.message.reply_text(
                "Виникла помилка. Повертаюсь до головного меню...",
                reply_markup=ReplyKeyboardMarkup(MAIN_MENU_KEYBOARD, resize_keyboard=True)
            )
    except:
        pass

async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle exit from any conversation mode."""
    user_id = update.effective_user.id
    
    # Clear user state
    if user_id in user_states:
        user_states[user_id]['mode'] = None
    
    # Return to main menu
    reply_markup = ReplyKeyboardMarkup(MAIN_MENU_KEYBOARD, resize_keyboard=True)
    await update.message.reply_text("Повертаємось до головного меню:", reply_markup=reply_markup)

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
