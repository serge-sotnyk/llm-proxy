import asyncio
import time
import httpx
from fastapi import FastAPI, Request, HTTPException, Response
from typing import List

# Конфигурация приложения и целевого API
# Список API-ключей, которые будут использоваться по схеме round-robin
API_KEYS = ["your_api_key1", "your_api_key2", "your_api_key3"]
# Лимит запросов для каждого API-ключа (15 запросов в минуту)
RATE_LIMIT = 15
# URL целевого API (например, API Google Gemini или другой API)
TARGET_API_URL = "https://api.example.com/endpoint"

class APIKeyManager:
    """
    Класс для управления API-ключами с механизмом round-robin и ограничением запросов (rate limiting).
    Для каждого ключа в памяти ведется статистика: количество запросов и время начала текущего окна.
    """
    def __init__(self, api_keys: List[str], rate_limit: int, window: int = 60):
        self.api_keys = api_keys
        self.rate_limit = rate_limit
        self.window = window  # Интервал окна в секундах (60 секунд = 1 минута)
        self.lock = asyncio.Lock()
        # Инициализируем для каждого ключа счетчик и время начала окна
        self.stats = {key: {"count": 0, "window_start": time.time()} for key in api_keys}
        self.index = 0  # Текущий индекс для round-robin

    async def get_available_key(self) -> str:
        """
        Возвращает доступный API-ключ, который не превысил лимит запросов.
        Если лимит для выбранного ключа исчерпан, пробует следующие.
        Если все ключи исчерпаны, ожидает окончания минимального времени ожидания.
        """
        async with self.lock:
            for _ in range(len(self.api_keys)):
                key = self.api_keys[self.index]
                stat = self.stats[key]
                current_time = time.time()
                # Если время текущего окна истекло, сбрасываем счетчик и обновляем время окна
                if current_time - stat["window_start"] >= self.window:
                    stat["count"] = 0
                    stat["window_start"] = current_time
                # Если лимит еще не исчерпан, используем этот ключ
                if stat["count"] < self.rate_limit:
                    stat["count"] += 1
                    # Обновляем индекс для round-robin
                    self.index = (self.index + 1) % len(self.api_keys)
                    return key
                # Переходим к следующему ключу
                self.index = (self.index + 1) % len(self.api_keys)
            # Если все ключи исчерпаны, вычисляем минимальное время ожидания для сброса лимита
            wait_times = []
            current_time = time.time()
            for key in self.api_keys:
                stat = self.stats[key]
                wait_time = self.window - (current_time - stat["window_start"])
                if wait_time < 0:
                    wait_time = 0
                wait_times.append(wait_time)
            min_wait = min(wait_times)
        # Ждем необходимое минимальное время и повторяем попытку
        await asyncio.sleep(min_wait)
        return await self.get_available_key()

# Инициализируем менеджер API-ключей
key_manager = APIKeyManager(API_KEYS, RATE_LIMIT)

# Создаем экземпляр FastAPI
app = FastAPI(title="Proxy API Gateway")

@app.post("/proxy")
@app.get("/proxy")
@app.put("/proxy")
@app.delete("/proxy")
@app.patch("/proxy")
async def proxy(request: Request):
    """
    Обработчик входящих запросов.
    Перенаправляет запрос к целевому API с подстановкой API-ключа, осуществляет ротацию ключей
    и следит за превышением лимита запросов.
    """
    # Получаем доступный API-ключ согласно алгоритму round-robin и rate limiting
    api_key = await key_manager.get_available_key()

    # Формируем заголовки запроса, добавляя API-ключ (в данном случае в поле Authorization)
    headers = dict(request.headers)
    headers["Authorization"] = f"Bearer {api_key}"

    # Читаем тело запроса, если оно присутствует
    body = await request.body()

    async with httpx.AsyncClient() as client:
        try:
            # Отправляем запрос к целевому API, используя тот же HTTP-метод, передавая заголовки, параметры и тело запроса
            response = await client.request(
                method=request.method,
                url=TARGET_API_URL,
                headers=headers,
                params=dict(request.query_params),
                content=body,
                timeout=10.0
            )
        except httpx.RequestError as exc:
            # Обработка ошибок при запросе к целевому API; даже неудачные запросы учитываются в лимите
            raise HTTPException(status_code=502, detail=f"Ошибка при обращении к целевому API: {exc}") from exc

    # Возвращаем ответ клиенту, сохраняя статус-код и тело ответа
    return Response(content=response.content, status_code=response.status_code, headers=response.headers)

# Пример запуска сервиса:
# uvicorn proxy_app:app --host 0.0.0.0 --port 8000

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("proxy_app:app", host="0.0.0.0", port=8000, reload=True)