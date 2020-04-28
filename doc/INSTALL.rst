Installing IdeaLoom
===================

Prerequisites
-------------

IdeaLoom has been tested on Ubuntu (esp. xenial and trusty), Debian (jessie and stretch) and Mac OS (10.9 onwards.) We recommend ubuntu xenial or debian stretch for production environments. In what follows, we'll assume python3.5 is installed on linux environments, and python3.6 on mac environments, but either version is suitable.

-  On Mac OS X 10.9.2: The system python is incompatible with the clang
   5.1. You need to remove all occurences of ``-mno-fused-madd`` in
   ``/System/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/_sysconfigdata.py``.
   Also renew (or delete) the corresponding ``.pyc``, ``.pyo`` files.

-  For production on linux using nginx/uwsgi you need the following ppa
   - Necessary for both saucy 13.10, raring 13.04, trusty 14.04
   - Not needed for vivid 15.04 and later (incl. xenial.)

.. code:: sh

   apt-add-repository ppa:chris-lea/uwsgi
   apt-get install nginx uwsgi uwsgi-plugin-python3

Homebrew on Mac
~~~~~~~~~~~~~~~

On mac, install Homebrew by following the instructions at http://brew.sh ; or simply paste the following in the terminal:

.. code:: sh

    ruby -e "$(curl -fsSL https://raw.github.com/mxcl/homebrew/go/install)"

Make sure `/usr/local/bin` is in your `$PATH`.

Install python a SSH server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You need python (3.6+) and a SSH server installed.
Here is how to install the ssh server on Mac and on Ubuntu.

On Mac
++++++

Install the homebrew python and fabric:

.. code:: sh

    brew install python

MacOS has a SSH server installed. To activate it, go to System Preferences in the Apple Menu, then to the Sharing tab. Ensure the "Remote login" checkbox is active.

On Ubuntu
+++++++++

You can get all that you need to bootstrap with:

.. code:: sh

    apt-get install python3 git openssh-server sudo

Setting up a production user
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On a production machine, you would want to create a user account dedicated to idealoom (we'll call it ``idealoom_user`` in what follows). This user will not be sudoer, but will have some specific sudo permissions. We suggest defining a group (``idealoom_group``) for all idealoom users, in case there are multiple installs. This also assumes that the nginx web server runs in group ``www-data``.

Run this as a sudoer user:

.. code:: sh

    sudo apt-get install nginx uwsgi uwsgi-plugin-python3
    sudo addgroup idealoom_group
    sudo adduser idealoom_user
    sudo usermod -G www-data -G idealoom_group idealoom_user

Note: For a simple single-server setup, it is also possible to use the ``www-data`` user directly, and to put idealoom in ``/var/www``.

On a development machine, we assume the idealoom server runs under your own user.

Postgres
~~~~~~~~

By default, postgres will not use passwords from postgres users who connect through the Unix socket domain (versus a network connection).
So if you want to make your database to be safer and ask for password anyway, edit your /etc/postgresql/9.5/main/pg_hba.conf file and

.. code:: ini

    # replace
    local   all             all                                peer
    # by
    local   all             all                                md5


and then run

.. code:: sh

    sudo service postgresql restart



Installing the application
--------------------------

First, choose a directory for installation (which we will call application root). If you install from source, it may be the same as the git directory. These commands should be run as the ``idealoom_user`` if you created one. (You may use ``sudo -u idealoom_user -i`` to do so.)


Installing from wheel
~~~~~~~~~~~~~~~~~~~~~

.. code:: sh

    mkdir idealoom
    cd idealoom
    python3 -mvirtualenv -p /usr/bin/python3 venv
    source ./venv/bin/activate
    pip install --no-index --find-links=https://idealoom.org/wheelhouse idealoom
    ln -s venv/lib/python3.5/site-packages/idealoom/fabfile.py .

The last step allows fabric to use the fabfile embedded in the package when running from the application root.

Installing from source
~~~~~~~~~~~~~~~~~~~~~~


.. code:: sh

    git clone https://github.com/conversence/idealoom.git
    cd idealoom
    python3 -mvirtualenv -p /usr/bin/python3 venv
    source ./venv/bin/activate
    pip install Fabric3 future cython
    fab -f assembl/fabfile.py -c assembl/configs/develop.rc bootstrap_from_checkout

Ontology Submodule
++++++++++++++++++

The ontology module is a git submodule. As a result, after pulling in changes,
update with the following:

.. code:: sh

    git submodule update --init

Setting initial parameters
--------------------------

You will create a ``local.rc`` file in the idealoom project root, which will be based on either ``base_env.rc`` (production) or ``develop.rc`` or ``mac.rc`` (development). The base environment is set in the ``_extends`` parameter. So in a basic production environment, it should contain at least:

.. code:: ini

    _extends = base_env.rc
    public_hostname = your_hostname


In a development environment, it might be as simple as ``_extends = develop.rc``.

The rc file format is described in the :doc:`configuration` document.

Here are a few more values you should set:

* ``idealoom_admin_email`` to your email
* ``_user`` to the username of the idealoom process

Some optional fabric commands require sudo privileges; you could do these commands as root, or designate a sudo-capable account as ``sudoer`` in the ``local.rc`` file. (Avoid making the ``idealoom_user`` a sudoer.) Fabric will then login as this sudo-capable user.

Sentry
~~~~~~

If you're using Sentry_ to monitor, you need to set the following keys, as described in `Sentry documentation`_. 

* ``*sentry_host``
* ``*sentry_key``
* ``*sentry_secret``
* ``*sentry_id``

If you're not using Sentry, you would want to include ``no_sentry.ini`` in the ``ini_files`` value chain, as described in :doc:`configuration`.

Postgres
~~~~~~~~

You need to set a postgres user for the idealoom database. It is simplest if this postgres user has the same name as the unix ``idealoom_user`` account. This database user needs to have ``create database`` permissions. This user can be created with the ``fab check_and_create_database_user`` command, but this then requires the password of the postgres root account in the ``postgres_db_password`` configuration variable. (This account is usually ``postgres`` on linux, or the user's account on mac.)

It is also a good idea to set a different password for the idealoom postgres account.

* ``*postgres_db_password``: optional
* ``*db_user``: usually ``idealoom_user``
* ``*db_password``: set to any value
* ``*db_database``: optional
* ``*db_host``: if different from localhost

A note on vagrant
~~~~~~~~~~~~~~~~~

If you use vagrant, we have a few processes that expect to use socket
files in %(here)s. Vagrant does not allow creating sockets in a shared
folder; so if you insist on using vagrant, make sure to move sockets
locations. Some are defined in circusd.conf.tmpl, and changes.socket
is defined in the .ini files.

Multiple environments
~~~~~~~~~~~~~~~~~~~~~

If you want to run multiple environments on your machine, some of the configuration parameters in each ``local.rc`` must have different values.

The variables that have to be different between instances are the
following (for convenience they are marked with UNIQUE\_PER\_SERVER in
``base_env.rc`` and ``develop.rc``):

.. code:: ini

    public_port = 6543
    changes_socket = ipc:///tmp/idealoom_changes/0
    changes_websocket_port = 8085
    redis_socket = 0
    webpack_port = 8080
    server:main__port = 6543

Most of these are ports, and it should be easy to find an unoccupied
port; in the case of ``changes.socket``, you simply need a different
filename, and in the case of ``celery_task.*.broker``, the final number
has to be changed to another low integer.

The ``public_port`` field (located in ``app:idealoom`` section) is the actual port used by the UWSGI server which is rerouted through the reverse proxy served by nginx. For production context, use 80.
There is also a ``port`` field in ``server:main`` section, which defaults to 6543. If not proxied by nginx or something, ``port`` needs to match ``public_port``.

Also, set the ``uid`` field of the ``uwsgi`` section of your ini file to the username of the unix user you created above. For example: ``uid = idealoom_user``
If you have not added this user to the www-data group as advised previously (or to a group which is common with the ngnix user), then you also have to set the ``gid`` field to a common group name.

If you do not have an SSL certificate, then you have to set ``accept_secure_connection = false`` and ``require_secure_connection = false`` (because if you set ``accept_secure_connection = true``, then the login page on IdeaLoom will try to show using https, which will not work).


Getting the server ready
------------------------

The next command installs various components. It must be run as root on linux, or the ``_sudoer`` parameter must be set in the ``local.rc`` file:

.. code:: sh

    fab -f assembl/fabfile.py -c local.rc install_single_server

You must omit the ``-f assembl/fabfile.py`` flag if you have installed from a wheel, as fabric will use the symbolic link. This holds for the next few commands.

Note: If on Mac, command fab -c assembl/configs/develop.rc install_single_server outputs "Low level socket error: connecting to host localhost on port 22: Unable to connect to port 22 on 127.0.0.1", you have to go to System preferences > Sharing > check "Enable remote login", and retry the command.

Again as the ``idealoom_user``:

If you're running from source:

.. code:: sh

    fab -f assembl/fabfile.py -c local.rc bootstrap_from_checkout

If you're running from wheel:

.. code:: sh

    fab -c local.rc bootstrap_from_wheel


Note: If you get the following error: ``fabric.exceptions.NetworkError: Incompatible ssh server (no acceptable macs)`` Then you'll need to reconfigure your ssh server


Running
-------

Note: postgres, openssl, memcached and redis must be running already.

.. code:: sh

    source venv/bin/activate
    circusd circusd.conf

Creating a user the first time you run IdeaLoom (so you have a
superuser):

.. code:: sh

    idealoom-add-user --email your_email@email.com --name "Your Name" --username desiredusername --password yourpassword local.ini

Note: Just running ``$venv/bin/circusd`` will NOT work, as celery will
run command line tools, thus breaking out of the environment. You need
to run ``source venv/bin/activate`` from the same terminal before running
the above

Note: If you do not want to ``source activate`` every time, you can hook it in your shell using something like `Autoenv <https://github.com/kennethreitz/autoenv>`_. Another option is to use `VirtualenvWrapper <https://bitbucket.org/virtualenvwrapper/virtualenvwrapper>`_ and its `Helper <https://justin.abrah.ms/python/virtualenv_wrapper_helper.html>`_. At least one of us uses `VirtualFish <https://github.com/adambrenecki/virtualfish>`_ with auto-activation.


On subsequent runs, just make sure circusd is running.

In development
~~~~~~~~~~~~~~

Then, start the development server with this command:

.. code:: sh

    env CIRCUSCTL_ENDPOINT=ipc://`pwd`/var/run/circus_endpoint circusctl start pserve

You can now type http://localhost:6543 in your browser and log in using the credentials you created.

Final production tasks
----------------------

Nginx connection (production)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: sh

    idealoom-ini-files template -o {{idealoom.yourdomain.com}} local.rc nginx_default.jinja2

As root: put that ``{{idealoom.yourdomain.com}}`` file in ``/etc/nginx/sites_available``. Activate this site, using:

.. code:: sh

    cd /etc/nginx/sites-enabled/
    ln -s /etc/nginx/sites-available/{{idealoom.yourdomain.com}} .

Test that your configuration file works, by running:

.. code:: sh

    /usr/sbin/nginx -t

Restart nginx:

.. code:: sh

    /etc/init.d/nginx restart

Securing nginx
~~~~~~~~~~~~~~

TODO

Automating Idealoom startup
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Copy the content of ``doc/sample_systemd_script/idealoom.service`` into ``/etc/systemd/system/idealoom.service``, and modify fields IDEALOOM_PATH, User and Description.

.. code:: sh

    systemctl enable idealoom
    service idealoom restart


Mail setup
~~~~~~~~~~

You may set up an external or internal SMTP server (TODO), an external IMAP server (TODO), and Piwik.

The :doc:`spam` document explains how to minimize the risk of email sent by idealoom being identified as spam.
The :doc:`vmm` document explains how to set up an internal IMAP server.


Backups
~~~~~~~

See :doc:`backups`


Updating an environment
-----------------------

.. code:: sh

    cd ~/idealoom
    #Any git operations (ex:  git pull)
    fab -c assembl/configs/develop.rc app_compile
    $venv/bin/circusctl start pserve webpack

You can monitor any of the processes, for example pserve, with these
commands:

.. code:: sh

    tail -f var/log/pserve.log
    tail -f var/log/pserve.err.log

In production:

.. code:: sh

    #(Instead of dev:*. You may have to stop dev:*)
    $venv/bin/circusctl start uwsgi

Updating an environment after switching branch locally (will regenerate
css, all compiled files, update dependencies, database schema, etc.):

.. code:: sh

    fab -c assembl/configs/develop.rc app_compile

Updating an environment to it's specified branch, tag or revision:

.. code:: sh

    cd ~/idealoom
    fab -c assembl/configs/develop.rc app_fullupdate

Schema migrations
~~~~~~~~~~~~~~~~~

Upgrade to latest manally:

.. code:: sh

    alembic -c local.ini upgrade head

Create a new one:

.. code:: sh

    alembic -c local.ini revision -m "Your message"
    Make sure to verify the generated code...

Autogeneration (--autogenerate) isn't supported since we don't have full
reflexion support in virtuoso's sqlalchemy driver.

.. _Sentry: https://sentry.io/welcome/
.. _`Sentry documentation`: https://docs.sentry.io/quickstart/?platform=python#configure-the-sdk
