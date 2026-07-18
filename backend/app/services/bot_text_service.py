from dataclasses import dataclass
from html.parser import HTMLParser
import logging
from string import Formatter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BotTextSetting
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)

TELEGRAM_HTML_TAGS = {
    "a",
    "b",
    "blockquote",
    "code",
    "del",
    "em",
    "i",
    "ins",
    "pre",
    "s",
    "span",
    "strike",
    "strong",
    "tg-emoji",
    "tg-spoiler",
    "u",
}


class TelegramHTMLValidator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.open_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag not in TELEGRAM_HTML_TAGS:
            raise ValueError(f"Неподдерживаемый HTML-тег: <{tag}>")
        self.open_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.open_tags or self.open_tags[-1] != tag:
            raise ValueError(f"Нарушен порядок закрытия HTML-тега: </{tag}>")
        self.open_tags.pop()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        raise ValueError(f"Самозакрывающийся HTML-тег не поддерживается: <{tag}/>")

    def validate(self, text: str) -> None:
        try:
            self.feed(text)
            self.close()
        except (ValueError, AssertionError) as exc:
            raise ValueError(str(exc) or "Некорректная HTML-разметка") from exc
        if self.open_tags:
            raise ValueError(f"Не закрыт HTML-тег: <{self.open_tags[-1]}>")


@dataclass(frozen=True)
class BotTextDefinition:
    key: str
    category: str
    title: str
    description: str
    default: str
    variables: tuple[str, ...] = ()


BOT_TEXTS = (
    BotTextDefinition(
        "welcome",
        "Основные",
        "Приветствие /start",
        "Первое сообщение новому пользователю.",
        """<b>🎵 Добро пожаловать в Prod.by!</b>

Это закрытое сообщество, объединяющее специалистов музыкальной индустрии и смежных творческих направлений.

🎧 Здесь мы собираем не только артистов, продюсеров, битмейкеров и звукорежиссеров, но и дизайнеров, операторов, монтажеров, организаторов и всех, кто участвует в создании и продвижении музыкальных проектов.

📝 Для вступления необходимо пройти небольшую анкету. После проверки администрацией вы получите уведомление о результате рассмотрения заявки.

Нажмите <b>«Подать заявку»</b>, чтобы начать 👇""",
    ),
    BotTextDefinition(
        "access_banned",
        "Основные",
        "Подача заявок заблокирована",
        "Ответ заблокированному пользователю.",
        "⛔ <b>Доступ ограничен</b>\n\nВы не можете подать новую заявку в Prod.by.",
    ),
    BotTextDefinition(
        "already_member",
        "Основные",
        "Пользователь уже в группе",
        "Ответ участнику сообщества при повторном /start.",
        "✅ <b>Вы уже состоите в Prod.by</b>\n\nПовторная заявка не требуется — доступ к сообществу у вас уже есть.",
    ),
    BotTextDefinition(
        "active_application_pending",
        "Основные",
        "Заявка рассматривается",
        "Ответ при попытке создать дубликат заявки.",
        "⏳ <b>Заявка №{application_id} уже на рассмотрении</b>\n\nПовторно заполнять анкету не нужно. Мы пришлем решение в этот чат.",
        ("application_id",),
    ),
    BotTextDefinition(
        "active_application_approved",
        "Основные",
        "Заявка уже одобрена",
        "Ответ при повторном запуске после одобрения.",
        "✅ <b>Заявка №{application_id} уже одобрена</b>\n\nИспользуйте ссылку из сообщения об одобрении. Если она перестала действовать, обратитесь к администрации.",
        ("application_id",),
    ),
    BotTextDefinition(
        "admin_panel",
        "Основные",
        "Панель управления",
        "Сообщение по команде /admin.",
        "⚙️ <b>Панель управления</b>",
    ),
    BotTextDefinition(
        "admin_access_denied",
        "Основные",
        "Нет доступа к панели",
        "Ответ на /admin без прав.",
        "⛔ <b>Доступ запрещен</b>",
    ),
    BotTextDefinition(
        "question_prompt",
        "Анкета",
        "Шаблон вопроса",
        "Обертка каждого вопроса анкеты.",
        "💬 <b>{question}</b>\n\n<i>Шаг {step} из {total}</i>\n\n{help_text}",
        ("question", "step", "total", "help_text"),
    ),
    BotTextDefinition(
        "question_default_help",
        "Анкета",
        "Подсказка по умолчанию",
        "Используется, если у вопроса нет своей подсказки.",
        "Отправьте ответ сообщением.",
    ),
    BotTextDefinition(
        "number_hint",
        "Анкета",
        "Подсказка для числа",
        "Добавляется к вопросам с числовым ответом.",
        "<i>Ответ должен быть числом.</i>",
    ),
    BotTextDefinition(
        "choice_hint",
        "Анкета",
        "Подсказка для выбора",
        "Добавляется к вопросу с готовыми вариантами ответа.",
        "<i>Выберите один вариант кнопкой ниже.</i>",
    ),
    BotTextDefinition(
        "text_answer_required",
        "Анкета",
        "Пустой ответ",
        "Ответ, если пользователь не прислал текст.",
        "⚠️ <b>Нужен текстовый ответ</b>\n\nОтправьте ответ обычным сообщением.",
    ),
    BotTextDefinition(
        "number_answer_required",
        "Анкета",
        "Ожидается число",
        "Ответ при неверном числовом значении.",
        "⚠️ <b>Нужно число</b>\n\nНапример: <b>24</b>.",
    ),
    BotTextDefinition(
        "choice_answer_required",
        "Анкета",
        "Ожидается выбор",
        "Ответ, если пользователь пишет текст вместо нажатия варианта.",
        "⚠️ <b>Выберите один из вариантов</b>\n\nИспользуйте кнопки под вопросом.",
    ),
    BotTextDefinition(
        "choice_expired",
        "Анкета",
        "Устаревшая кнопка",
        "Короткое уведомление при нажатии кнопки от прошлого вопроса.",
        "Этот вопрос уже неактуален",
    ),
    BotTextDefinition(
        "choice_missing",
        "Анкета",
        "Вариант не найден",
        "Короткое уведомление, если вариант был изменен администратором.",
        "Вариант ответа не найден",
    ),
    BotTextDefinition(
        "questionnaire_flow_error",
        "Анкета",
        "Ошибка ветвления",
        "Показывается при некорректном циклическом переходе.",
        "⚠️ <b>Не удалось продолжить анкету</b>\n\nСообщите администрации и попробуйте позже.",
    ),
    BotTextDefinition(
        "age_invalid",
        "Анкета",
        "Некорректный возраст",
        "Ответ для возраста вне допустимого диапазона.",
        "⚠️ <b>Проверьте возраст</b>\n\nДопустимое значение: от 1 до 120.",
    ),
    BotTextDefinition(
        "portfolio_prompt",
        "Анкета",
        "Добавление работ",
        "Приглашение приложить файлы и ссылки.",
        "📎 <b>Добавьте примеры работ</b>\n\n<i>Шаг {step} из {total}</i>\n\nПрикрепите до {max_attachments} файлов или ссылок. Размер одного файла — не более <b>10 МБ</b>. Можно продолжить без вложений — нажмите <b>«Пропустить вложения»</b>.",
        ("step", "total", "max_attachments"),
    ),
    BotTextDefinition(
        "attachment_limit",
        "Анкета",
        "Лимит вложений",
        "Ответ после достижения максимума файлов.",
        "📦 <b>Лимит достигнут</b>\n\nДобавлено {max_attachments} вложений. Нажмите <b>«Готово»</b>.",
        ("max_attachments",),
    ),
    BotTextDefinition(
        "attachment_unrecognized",
        "Анкета",
        "Вложение не распознано",
        "Ответ на неподдерживаемое сообщение.",
        "⚠️ <b>Не удалось распознать вложение</b>\n\nОтправьте файл, аудио, видео, фото или ссылку. Для завершения нажмите <b>«Готово»</b>.",
    ),
    BotTextDefinition(
        "attachment_check_failed",
        "Анкета",
        "Не проверен размер",
        "Ошибка проверки файла через Telegram.",
        "⚠️ <b>Не удалось проверить размер файла</b>\n\nПопробуйте отправить файл еще раз или продолжите без него.",
    ),
    BotTextDefinition(
        "attachment_too_large",
        "Анкета",
        "Файл слишком большой",
        "Ответ для файла больше 10 МБ.",
        "⚠️ <b>Файл слишком большой</b>\n\nРазмер одного файла не должен превышать <b>10 МБ</b>. Отправьте файл меньшего размера или продолжите без него.",
    ),
    BotTextDefinition(
        "attachment_added",
        "Анкета",
        "Вложение добавлено",
        "Подтверждение после добавления файла или ссылки.",
        "✅ <b>Вложение добавлено</b>\n\nСейчас в заявке: <b>{count} из {max_attachments}</b>. Можно отправить еще или нажать <b>«Готово»</b>.",
        ("count", "max_attachments"),
    ),
    BotTextDefinition(
        "user_unknown",
        "Анкета",
        "Пользователь не определен",
        "Редкая ошибка Telegram-профиля.",
        "⚠️ <b>Не удалось определить пользователя</b>\n\nОтправьте /start и попробуйте еще раз.",
    ),
    BotTextDefinition(
        "submit_banned",
        "Анкета",
        "Блокировка при отправке",
        "Ответ, если блокировка появилась во время заполнения.",
        "⛔ <b>Доступ ограничен</b>\n\nВы не можете отправить заявку в Prod.by.",
    ),
    BotTextDefinition(
        "submit_attachment_too_large",
        "Анкета",
        "Ошибка размера при отправке",
        "Повторная серверная проверка вложений.",
        "⚠️ <b>Файл слишком большой</b>\n\nУдалите файл больше 10 МБ и попробуйте снова.",
    ),
    BotTextDefinition(
        "application_submitted",
        "Анкета",
        "Заявка отправлена",
        "Финальное подтверждение анкеты.",
        "🎉 <b>Заявка №{application_id} отправлена</b>\n\nАдминистрация рассмотрит ее и пришлет результат в этот чат.",
        ("application_id",),
    ),
    BotTextDefinition(
        "application_approved",
        "Решения",
        "Заявка одобрена",
        "Основная часть уведомления об одобрении.",
        "🎉 <b>Ваша заявка одобрена!</b>\n\nДобро пожаловать в сообщество Prod.by.",
    ),
    BotTextDefinition(
        "assigned_roles",
        "Решения",
        "Назначенные роли",
        "Добавляется только при выборе ролей.",
        "🎭 Назначенные роли: <b>{roles}</b>",
        ("roles",),
    ),
    BotTextDefinition(
        "admin_comment",
        "Решения",
        "Комментарий администрации",
        "Добавляется к решению или блокировке при наличии комментария.",
        "💬 <b>Комментарий администрации</b>\n{comment}",
        ("comment",),
    ),
    BotTextDefinition(
        "invite_ready",
        "Решения",
        "Ссылка на вход создана",
        "Пояснение к персональной ссылке.",
        "🔗 Ссылка действует <b>7 дней</b> и рассчитана на одно вступление.",
    ),
    BotTextDefinition(
        "invite_unavailable",
        "Решения",
        "Ссылка недоступна",
        "Добавляется, если Telegram не создал ссылку.",
        "⚠️ Ссылка на вход пока недоступна. Администрация должна проверить права бота.",
    ),
    BotTextDefinition(
        "application_rejected",
        "Решения",
        "Заявка отклонена",
        "Основная часть уведомления об отказе.",
        "📩 <b>Решение по заявке</b>\n\nВаша заявка в сообщество Prod.by отклонена.",
    ),
    BotTextDefinition(
        "user_banned",
        "Решения",
        "Пользователь заблокирован",
        "Уведомление после блокировки администратором.",
        "⛔ <b>Доступ к Prod.by заблокирован.</b>",
    ),
    BotTextDefinition(
        "moderation_banned",
        "Модерация",
        "Сообщение заблокированному",
        "Короткое уведомление в теме перед автоудалением.",
        "⛔ <b>Доступ к сообществу заблокирован</b>\n{mention}, вы не можете публиковать сообщения.",
        ("mention",),
    ),
    BotTextDefinition(
        "moderation_missing_role",
        "Модерация",
        "Нет роли для темы",
        "Короткое уведомление в теме перед автоудалением.",
        "⛔ <b>Нет доступа к публикации</b>\n{mention}, для этой темы нужна разрешенная роль.{timeout}",
        ("mention", "timeout"),
    ),
    BotTextDefinition(
        "moderation_timeout",
        "Модерация",
        "Таймаут за нарушение",
        "Добавляется, если Telegram применил ограничение.",
        "Таймаут на отправку сообщений: <b>{seconds} сек.</b>",
        ("seconds",),
    ),
)

BOT_TEXTS_BY_KEY = {item.key: item for item in BOT_TEXTS}


def validate_bot_text(key: str, text: str) -> None:
    definition = BOT_TEXTS_BY_KEY.get(key)
    if definition is None:
        raise ValueError("Неизвестный текст бота")
    if not text.strip():
        raise ValueError("Текст не может быть пустым")
    if len(text) > 4096:
        raise ValueError("Текст не должен превышать 4096 символов")

    TelegramHTMLValidator().validate(text)

    variables: set[str] = set()
    try:
        for _, field_name, _, _ in Formatter().parse(text):
            if field_name:
                variables.add(field_name)
    except ValueError as exc:
        raise ValueError("Проверьте парные фигурные скобки в тексте") from exc

    unknown = variables - set(definition.variables)
    if unknown:
        raise ValueError(f"Недопустимые переменные: {', '.join(sorted(unknown))}")
    missing = set(definition.variables) - variables
    if missing:
        raise ValueError(f"Не удаляйте переменные: {', '.join(sorted(missing))}")


async def get_bot_text_value(session: AsyncSession, key: str) -> str:
    definition = BOT_TEXTS_BY_KEY[key]
    setting = await session.get(BotTextSetting, key)
    return setting.text if setting is not None else definition.default


async def render_bot_text(key: str, **values: object) -> str:
    async with SessionLocal() as session:
        template = await get_bot_text_value(session, key)
    try:
        validate_bot_text(key, template)
    except ValueError:
        logger.exception("Invalid bot text override for %s; using default", key)
        template = BOT_TEXTS_BY_KEY[key].default
    return template.format(**values)


async def get_bot_text_overrides(session: AsyncSession) -> dict[str, BotTextSetting]:
    result = await session.execute(select(BotTextSetting))
    return {item.key: item for item in result.scalars().all()}
