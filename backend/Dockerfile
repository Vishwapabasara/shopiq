FROM python:3.12-slim

WORKDIR /app

# System deps for WeasyPrint (PDF generation) + BeautifulSoup
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 libpangocairo-1.0-0 \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install BeautifulSoup for HTML parsing in audit rules
RUN pip install --no-cache-dir beautifulsoup4==4.12.3 lxml==5.2.2

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
