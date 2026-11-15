# **بحثُ الأماكن من القرص** (قرارُ المالك ٢٠٢٦-١١-١٥) — بايثون وSQLite وحدَهما، بلا تبعيّة؛ والفهرسُ ملفٌّ يُثبَّت للقراءة من `/data`
FROM python:3.12-alpine
RUN adduser -D -u 10001 places
WORKDIR /app
COPY server.py .
USER places
ENV PORT=8090 PLACES_INDEX=/data/places.sqlite PYTHONUNBUFFERED=1
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8090/health',timeout=4)"
CMD ["python", "-I", "server.py"]
