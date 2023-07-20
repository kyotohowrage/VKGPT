import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import openai
import time
import threading
import random

# Здесь вставьте ваш API-ключ GPT-3.5
gpt_api_key = "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"

# Время задержки между запросами (в секундах) для каждого пользователя
request_delay = 2
# Максимальное количество токенов в ответе
max_tokens = 2048
# Список запретных тем
forbidden_topics = [
    "кто ты",
    "почему ты здесь",
    "сколько тебе лет",
    "как тебя зовут",
    "где ты родился",
    "что ты делаешь",
    "какого цвета у тебя кожа",
    # Добавьте сюда другие запретные темы, если необходимо
]
# Словарь для хранения времени последнего запроса и предыдущего ответа для каждого пользователя
user_data = {}

def generate_gpt_response(message, context=None):
    openai.api_key = gpt_api_key

    prompt = message
    if context:
        prompt = f"{context}\n{message}"

    # Генерируем случайное значение temperature в диапазоне от 0.6 до 0.8
    temperature = round(random.uniform(0.6, 0.8), 1)

    try:
        response = openai.Completion.create(
            engine="text-davinci-003",  # Используем более быстрый движок
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            n=1,
        )

        generated_response = response.choices[0].text.strip()

        if not generated_response:
            return "Произошла ошибка при генерации ответа. Пожалуйста, повторите запрос."

        return generated_response

    except openai.error.RateLimitError:
        return "Ежедневный лимит запросов к API OpenAI исчерпан. Попробуйте позже."

def clear_context(user_id):
    user_data[user_id] = {}

def handle_incoming_messages(comunity_token):
    vk_session = vk_api.VkApi(token=comunity_token)
    vk = vk_session.get_api()

    longpoll = VkLongPoll(vk_session)

    def is_forbidden_topic(message):
        return any(topic in message.lower() for topic in forbidden_topics)

    def respond_to_message(event):
        current_time = time.time()

        try:
            user_message = event.text
            user_id = event.user_id

            # Проверяем, не входит ли вопрос в список запретных тем
            if is_forbidden_topic(user_message):
                response = "Извините, я не могу ответить на этот вопрос, так как это связано с моей личной информацией."

            elif user_message.strip().lower() == "#очистка":
                clear_context(user_id)
                response = "Контекст очищен."

            else:
                # Проверяем, обрабатывается ли в данный момент запрос от данного пользователя
                if user_id in user_data and "is_processing" in user_data[user_id] and user_data[user_id]["is_processing"]:
                    response = "Подождите когда я закончу с прошлым вопросом..."
                else:
                    # Устанавливаем флаг, что обрабатывается запрос от данного пользователя
                    user_data[user_id] = {"is_processing": True}

                    # Проверка времени прошедшего с момента последнего запроса для данного пользователя
                    elapsed_time = current_time - user_data.get(user_id, {}).get("last_request_time", 0)

                    if elapsed_time < request_delay:
                        # Задержка перед отправкой следующего запроса для данного пользователя
                        time.sleep(request_delay - elapsed_time)

                    # Отправка сообщения "Ищу ответ..." перед тем, как дать ответ
                    vk.messages.send(
                        peer_id=event.peer_id,
                        message="Ищу ответ...",
                        random_id=get_random_id(),
                    )

                    # Получение предыдущего ответа пользователя
                    context = user_data.get(user_id, {}).get("last_response")

                    # Получаем предсказание GPT-3 с учетом контекста
                    response = generate_gpt_response(user_message, context=context)

                    # Сбрасываем флаг обработки запроса
                    user_data[user_id]["is_processing"] = False

                    # Обновление контекста для данного пользователя
                    user_data[user_id]["last_response"] = response

            vk.messages.send(
                peer_id=event.peer_id,
                message=response,
                random_id=get_random_id(),
            )

        except Exception as e:
            print(f"Возникло исключение: {e}")
            # При возникновении исключения, перезапускаем бот снова
            handle_incoming_messages(comunity_token)

    # Максимальное количество параллельно обрабатываемых запросов
    max_threads = 5
    # Список для хранения потоков
    threads = []

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            # Если количество активных потоков меньше максимального, запустите новый поток
            if len(threads) < max_threads:
                thread = threading.Thread(target=respond_to_message, args=(event,))
                thread.start()
                threads.append(thread)

            # Проверьте статус всех потоков и удалите завершенные
            for thread in threads.copy():
                if not thread.is_alive():
                    threads.remove(thread)

if __name__ == "__main__":
    comunity_token = "vk1.a.1Kw54SwJgb_n57Z5aXt9eOyxiPQ3mPi1I58UfEiTLKyAc5GOt9r6t3dNMqUyoe8sqmxMiEbZmI4VVr0Yv8wrhjMT_7MOU_msPbKFego9umIikIpPCo2r93sSFPQED-nSHF4ZG1mGm1l9mNAGrIMR6G7Os_A2Oo93JRDmHTcs9JSNo7nQK6eJ0CwboRvWk96bAeIcoEbg58r33mXDSb1XhQ"  # Замените на токен вашего сообщества VK
    handle_incoming_messages(comunity_token)
