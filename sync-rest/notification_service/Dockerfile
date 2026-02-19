FROM python:3.12
WORKDIR /app
COPY . .
EXPOSE 8082
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "notification.py"]