FROM python:3.11-slim
RUN pip install python-telegram-bot requests
COPY bot.py .
CMD ["python3", "bot.py"]
