FROM python:3.12
WORKDIR /app
COPY . .
EXPOSE 8081
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "inventory.py"]