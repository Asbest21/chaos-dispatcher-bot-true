FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Создаем директорию для данных
RUN mkdir -p data/logs

# Запускаем
CMD ["python", "bot.py"]
