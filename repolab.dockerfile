FROM nvidia/cuda:8.0-cudnn6-devel-ubuntu16.04

ENV DEBIAN_FRONTEND noninteractive
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

RUN apt-get update && apt-get -yq dist-upgrade \
 && apt-get install -yq --no-install-recommends \
	locales python-pip cmake \
	python3-pip python3-setuptools git build-essential \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install jupyterlab bash_kernel \
 && python3 -m bash_kernel.install

ENV SHELL=/bin/bash \
	NB_USER=jovyan \
	NB_UID=1000 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8

ENV HOME=/home/${NB_USER}

RUN adduser --disabled-password \
	--gecos "Default user" \
	--uid ${NB_UID} \
	${NB_USER}

EXPOSE 8888
WORKDIR ${HOME}

CMD ["jupyter", "lab", "--no-browser", "--ip=0.0.0.0", "--NotebookApp.token=''"]

RUN apt-get update \
 && apt-get install -yq --no-install-recommends \
    python3-tk \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install  \
    tensorflow-gpu==1.4 \
    keras \
    matplotlib

COPY . ${HOME}
RUN chown -R ${NB_UID} ${HOME}
USER ${NB_USER}
RUN :
