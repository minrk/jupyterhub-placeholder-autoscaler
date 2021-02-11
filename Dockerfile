FROM python:3.9-alpine
ENV PIP_NO_CACHE_DIR=1
RUN python3 -m pip install --upgrade pip
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install -r /tmp/requirements.txt
COPY placeholderscaler /srv/placeholderscaler
WORKDIR /srv
CMD ["python3", "-m", "placeholderscaler"]
USER nobody
