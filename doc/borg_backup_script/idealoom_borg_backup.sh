#!/bin/sh

#You need to set these two environment variables, for example:
#IDEALOOM_PATH=/home/benoitg/development/idealoom
#REPOSITORY=www-data@coeus.ca:/media/backup/idealoom_backups.borg

BORG_PASSPHRASE='' borg init --encryption=keyfile $REPOSITORY || true
echo "Do not worry if the above command fails, it is expected to fail except the first time it is run"

cd $IDEALOOM_PATH
#In case the virtuoso file backup fails
fab env_dev database_dump
#Make sure we back up the database dump from the last deployment:
cp --dereference $IDEALOOM_PATH/assembl-virtuoso-backup.bp $IDEALOOM_PATH/assembl-virtuoso-backup-real.bp
NAME="`hostname`-`basename $IDEALOOM_PATH`-`date --iso-8601='minutes'`"
#set -x
borg create                             \
    $REPOSITORY::$NAME      \
    $IDEALOOM_PATH                               \
    --exclude $IDEALOOM_PATH/src                             \
    --exclude $IDEALOOM_PATH/venv                            \
    --exclude $IDEALOOM_PATH/vendor                            \
    --exclude $IDEALOOM_PATH/node_modules                            \
    --exclude $IDEALOOM_PATH/assembl/static/js/bower                            \
    --exclude $IDEALOOM_PATH/assembl/static/*/bower_components \
    --exclude $IDEALOOM_PATH/.git \
    --exclude '*.sass-cache' \
    --exclude $IDEALOOM_PATH/assembl_dumps \
    --exclude '*.pyc' \
    --progress \
    --stats
#    --verbose

rm $IDEALOOM_PATH/assembl-virtuoso-backup-real.bp
# Use the `prune` subcommand to maintain 7 daily, 4 weekly
# and 6 monthly archives.
borg prune --info --list --stats $REPOSITORY --keep-daily=7 --keep-weekly=4 --keep-monthly=6
