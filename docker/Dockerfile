FROM    debian:buster

ENV     DEBIAN_FRONTEND noninteractive
ARG	GITREPO=conversence/idealoom
ARG	GITBRANCH=main
ARG DOCKER_RC=assembl/configs/docker.rc
ARG BUILDING_DOCKER=true

RUN apt-get update && apt-get install -y \
            apt-utils \
            apt-transport-https \
            ca-certificates \
            locales \
            python3 \
            python3-pip \
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
           ssh -o StrictHostKeyChecking=no localhost uptime && \
           cat ~/.ssh/known_hosts >> ~idealoom_user/.ssh/known_hosts && \
           eval `ssh-agent` && \
           ssh-add ~/.ssh/id_rsa && \
           fab -f assembl/fabfile.py -c empty.rc install_assembl_server_deps && \
           rm -rf __pycache__ fabfile.pyc empty.rc && \
           /etc/init.d/ssh stop
RUN     /etc/init.d/ssh start && \
           sudo -i -u idealoom_user sh -c 'eval `ssh-agent` ; ssh-add ~/.ssh/id_rsa ; cd /opt/idealoom ; fab -f assembl/fabfile.py -c assembl/configs/docker.rc build_virtualenv' && \
           /etc/init.d/ssh stop
RUN     /etc/init.d/ssh start && \
           sudo -i -u idealoom_user sh -c 'eval `ssh-agent` ; ssh-add ~/.ssh/id_rsa ; cd /opt/idealoom ; fab -f assembl/fabfile.py -c assembl/configs/docker.rc app_update_dependencies' && \
           /etc/init.d/ssh stop
RUN        /etc/init.d/ssh start && \
           sudo -i -u idealoom_user sh -c 'eval `ssh-agent` ; ssh-add ~/.ssh/id_rsa ; cd /opt/idealoom ; . venv/bin/activate ; fab -c assembl/configs/docker.rc app_compile_nodbupdate ; fab -c assembl/configs/docker.rc set_file_permissions' && \
           /etc/init.d/ssh stop
CMD     /etc/init.d/ssh start && \
        sudo -i -u idealoom_user sh -c 'eval `ssh-agent` ; ssh-add ~/.ssh/id_rsa ; cd /opt/idealoom ; . venv/bin/activate ; fab -c assembl/configs/docker.rc docker_startup' && \
        tail -f /dev/null
