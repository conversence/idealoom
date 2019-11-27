#FROM    ubuntu:16.04
FROM    debian:stretch

ENV     DEBIAN_FRONTEND noninteractive
ARG	GITREPO=conversence/idealoom
ARG	GITBRANCH=master
ARG DOCKER_RC=assembl/configs/docker.rc
ARG BUILDING_DOCKER=true

RUN apt-get update && apt-get install -y \
            apt-utils \
            apt-transport-https \
            ca-certificates \
            locales \
            python3 \
            python3-pip \
            python3-paramiko \
            python3-future \
            python3-virtualenv \
            python3-wheel \
            python3-setuptools \
            python3-nose \
            python3-venv \
            python3-psycopg2 \
            git \
            openssh-server \
            sudo \
            net-tools \
            nodejs \
            monit \
            uwsgi \
            curl \
            fail2ban \
            uwsgi-plugin-python && \
            echo 'deb https://dl.yarnpkg.com/debian/ stable main' > /etc/apt/sources.list.d/yarn.list && \
            curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add - && \
            apt-get update && \
            apt-get install -y yarn && \
            pip3 install Fabric3
RUN         useradd -m -U -G www-data idealoom_user && \
            ssh-keygen -P '' -f ~/.ssh/id_rsa && cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys && \
            sudo -u idealoom_user -i sh -c "cd && mkdir .ssh && ssh-keygen -P '' -f .ssh/id_rsa && cat .ssh/id_rsa.pub >> .ssh/authorized_keys" && \
            cat ~/.ssh/id_rsa.pub >> ~idealoom_user/.ssh/authorized_keys
WORKDIR /opt
RUN     cd /opt ; set -x ; git clone -b $GITBRANCH https://github.com/$GITREPO.git ; chown -R idealoom_user:idealoom_user idealoom
WORKDIR /opt/idealoom
ENV LC_ALL C.UTF-8
ENV LC_CTYPE C.UTF-8
RUN     /etc/init.d/ssh start && \
           ssh-keyscan localhost && \
           touch empty.rc && \
           fab -f assembl/fabfile.py -c empty.rc install_assembl_server_deps && \
           rm -rf __pycache__ fabfile.py* empty.rc && \
           /etc/init.d/ssh stop
RUN     /etc/init.d/ssh start && \
           ssh-keyscan localhost && \
           fab -f assembl/fabfile.py -c $DOCKER_RC build_virtualenv && \
           /etc/init.d/ssh stop
RUN     /etc/init.d/ssh start && \
           ssh-keyscan localhost && \
           fab -f assembl/fabfile.py -c $DOCKER_RC app_update_dependencies && \
           /etc/init.d/ssh stop
RUN        /etc/init.d/ssh start && \
           ssh-keyscan localhost && \
           fab -c $DOCKER_RC app_compile_nodbupdate && \
           fab -c $DOCKER_RC set_file_permissions && \
           /etc/init.d/ssh stop
CMD     /etc/init.d/ssh start && \
        . venv/bin/activate && \
        fab -c $DOCKER_RC docker_startup && \
        tail -f /dev/null
