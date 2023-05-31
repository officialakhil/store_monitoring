FROM python:3.10-alpine3.17

WORKDIR /loop

COPY requirements/* requirements/

RUN pip install pip-tools 

RUN pip-sync requirements/prod.txt

COPY . .

RUN pip install gdown

RUN mkdir -p data

RUN gdown 1UIx1hVJ7qt_6oQoGZgb8B3P2vd1FD025 -O data/store_status.csv
RUN gdown 1va1X3ydSh-0Rt1hsy2QSnHRA4w57PcXg -O data/store_business_hours.csv
RUN gdown 101P9quxHoMZMZCVWQ5o-shonk2lgK1-o -O data/store_timezones.csv

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]