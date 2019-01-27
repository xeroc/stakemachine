# Download base image Ubuntu 18.04
FROM ubuntu:18.04

# Variable arguments to populate labels
ARG VERSION=0.9.5
ARG USER=dexbot

# Set ENV variables
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
ENV DEXBOT_HOME_PATH /home/$USER
ENV DEXBOT_REPO_PATH $DEXBOT_HOME_PATH/repo
ENV PATH $DEXBOT_HOME_PATH/.local/bin:$PATH

# Update Ubuntu Software repository
RUN	apt-get update
RUN	apt-get install -y software-properties-common
RUN add-apt-repository universe

# Install  dependencies
RUN apt-get install -y --install-recommends gcc libssl-dev python3-pip python3-dev python3-async whiptail inetutils-ping wget sudo git

# Create user and change workdir
RUN groupadd -r $USER && useradd -r -g $USER $USER
WORKDIR $DEXBOT_HOME_PATH
RUN chown -R $USER:$USER $DEXBOT_HOME_PATH
USER dexbot

RUN pip3 install --user pyyaml uptick tabulate ruamel.yaml sqlalchemy ccxt

# Download and Install  DEXBot

RUN git clone https://github.com/Codaone/DEXBot.git -b $VERSION $DEXBOT_REPO_PATH
RUN cd $DEXBOT_REPO_PATH && make install-user
RUN rm -rf $DEXBOT_REPO_PATH

