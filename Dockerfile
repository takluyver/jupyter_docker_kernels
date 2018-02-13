FROM python:3.6

RUN pip install --no-cache-dir ipykernel
WORKDIR /working

CMD ["python", "-m", "ipykernel_launcher", "-f", "/connect/kernel.json"]
