FROM python:3.10.16-slim-bookworm

COPY ./requirements.txt .

RUN pip install -r ./requirements.txt

COPY . .

CMD python app.py