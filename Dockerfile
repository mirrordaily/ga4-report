FROM python:3.11-slim-bookworm

COPY .  /usr/src/app/ga4-report
WORKDIR  /usr/src/app/ga4-report

RUN addgroup user && adduser -h /home/user -D user -G user -s /bin/sh

RUN apt-get update \
    && apt-get install -y gcc libc-dev libxslt-dev libxml2 libpq-dev

# Install packages in virtual environment if python version is >= 3.11
RUN python3 -m venv venv

RUN venv/bin/pip install --upgrade pip \
    && venv/bin/pip install -r requirements.txt

ENV LC_ALL="en_US.utf8"

EXPOSE 8080
CMD ["./venv/bin/uwsgi", "--ini", "server.ini"]