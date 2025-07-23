# -------- Base image: FSL 6.0.7.14 (Ubuntu) --------
FROM --platform=linux/amd64 vnmd/fsl_6.0.7.14

# -------- OS packages --------
#  - python2  : the interpreter
#  - curl     : pull get‑pip
#  - build‑essentials & libs so matplotlib etc. compile
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        python2 python2-dev curl build-essential \
        libfreetype6-dev libpng-dev fontconfig libxrender1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# -------- pip for Python 2.7 --------
RUN curl -sS https://bootstrap.pypa.io/pip/2.7/get-pip.py | python2

# -------- Python libraries --------
COPY requirements.txt /tmp/requirements.txt
RUN pip2 install --no-cache-dir -r /tmp/requirements.txt

# -------- ICA‑AROMA --------
WORKDIR /ICA-AROMA
COPY . /ICA-AROMA
ENTRYPOINT ["python2", "ICA_AROMA.py"]
