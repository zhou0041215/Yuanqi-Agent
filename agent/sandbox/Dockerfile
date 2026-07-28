FROM python:3.12-slim

RUN pip install --no-cache-dir \
    pandas==2.3.3 \
    numpy==2.3.4

RUN useradd --create-home --uid 10001 sandbox
COPY --chown=sandbox:sandbox runner.py /runner/runner.py
WORKDIR /workspace
USER sandbox

ENTRYPOINT ["python", "-I", "/runner/runner.py"]
