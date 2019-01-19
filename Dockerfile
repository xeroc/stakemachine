# Download base image Ubuntu 16.04
FROM ubuntu:16.04

# Update Ubuntu Software repository
RUN	apt-get update

RUN	apt-get install -y software-properties-common

RUN add-apt-repository  universe

# Install  dependencies and then DEXBot
RUN apt-get install -y --install-recommends gcc libssl-dev python3-pip python3-dev python3-async whiptail inetutils-ping wget

# Install app dependencies

RUN pip3 install pyyaml
RUN pip3 install uptick
RUN pip3 install tabulate

# Download and Install  DEXBot

RUN wget https://github.com/Codaone/DEXBot/archive/0.9.5.tar.gz
RUN tar zxvpf 0.9.5.tar.gz && rm -rf  0.9.5.tar.gz
RUN cd DEXBot-0.9.5
WORKDIR DEXBot-0.9.5
RUN make
RUN make install-user





