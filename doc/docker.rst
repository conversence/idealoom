Building a docker image
=======================

docker build --tag idealoom docker
docker run -d -p 8080:80 idealoom
firefox http://localhost:8080

The user is admin password admin

When developing the docker image, the build can be instructed to use
a git repository different from the official develop branch with:

sudo docker build --build-arg GITREPO=https://github.com/conversence/idealoom.git --build-arg GITBRANCH=master --tag idealoom --no-cache docker

Signed-off-by: Marc-Antoine Parent <maparent@acm.org>
Signed-off-by: Loic Dachary <loic@dachary.org>
