FROM python:3.10-alpine3.17

WORKDIR /loop

COPY requirements/* requirements/

RUN pip install pip-tools

RUN pip-sync requirements/prod.txt

COPY . .

CMD ["python", "-m", "arq", "jobs.WorkerSettings"]

