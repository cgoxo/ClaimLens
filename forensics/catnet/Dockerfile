# CAT-Net (Kwon et al.) for ClaimLens pixel forensics. Built by cloudbuild.yaml from this folder.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git libjpeg62-turbo-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cu121 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-build-isolation "jpegio==0.2.8"
COPY vendor/ /app/
COPY run_job.py test_run_job.py /app/
COPY weights/CAT_full_v2.pth.tar /app/weights/CAT_full_v2.pth.tar
ENTRYPOINT ["python", "/app/run_job.py"]
