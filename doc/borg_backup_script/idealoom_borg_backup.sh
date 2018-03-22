#!/bin/sh

#You need to set these two environment variables, for example:
#IDEALOOM_PATH=/home/benoitg/development/idealoom
#REPOSITORY=www-data@coeus.ca:/media/backup/idealoom_backups.borg

set -x BORG_RELOCATED_REPO_ACCESS_IS_OK=yes
BORG_PASSPHRASE='' borg init --encryption=keyfile $REPOSITORY || true
echo "Do not worry if the above command fails, it is expected to fail except the first time it is run"

cd $IDEALOOM_PATH
#In case the database backup fails
$IDEALOOM_PATH/venv/bin/assembl-db-manage local.ini backup
#Make sure we back up the database dump from the last deployment:
cp --dereference $IDEALOOM_PATH/idealoom-backup.pgdump $IDEALOOM_PATH/idealoom-backup-real.pgdump
NAME="`hostname`-`basename $IDEALOOM_PATH`-`date --iso-8601='minutes'`"
#set -x
borg create \
    $REPOSITORY::$NAME \
    $IDEALOOM_PATH \
    --exclude $IDEALOOM_PATH/src \
    --exclude $IDEALOOM_PATH/venv \
    --exclude $ASSEMBL_PATH/var/run \
    --exclude $ASSEMBL_PATH/var/db \
    --exclude $ASSEMBL_PATH/var/log \
    --exclude $ASSEMBL_PATH/var/sessions \
    --exclude $IDEALOOM_PATH/vendor \
    --exclude $IDEALOOM_PATH/assembl/static/js/bower \
    --exclude $IDEALOOM_PATH/assembl/static/node_modules \
    --exclude $IDEALOOM_PATH'/assembl/static/widget/*/bower_components' \
    --exclude $IDEALOOM_PATH/.git \
    --exclude '*.sass-cache' \
    --exclude $IDEALOOM_PATH/assembl_dumps \
    --exclude $IDEALOOM_PATH/idealoom_dumps \
    --exclude '*.pyc' \
    --progress \
    --stats
#    --verbose

rm $IDEALOOM_PATH/idealoom-backup-real.pgdump
# Use the `prune` subcommand to maintain 7 daily, 4 weekly
# and 6 monthly archives.
borg prune --info --list --stats $REPOSITORY --keep-daily=7 --keep-weekly=4 --keep-monthly=6
