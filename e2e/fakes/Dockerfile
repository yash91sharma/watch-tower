# Fake APIs (GitHub, LLM) for the E2E stack. The WT image has FastAPI and uvicorn, so the
# fakes use the same pinned versions. compose.test.yaml gives the WT image as "wt" and the
# app to run (for example fakes.github.app:app).
FROM wt
COPY github /e2e/fakes/github
COPY llm /e2e/fakes/llm
HEALTHCHECK --interval=2s --timeout=2s --retries=10 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=2)"]
ENTRYPOINT ["uvicorn", "--app-dir", "/e2e", "--host", "0.0.0.0", "--port", "8000"]
CMD []
