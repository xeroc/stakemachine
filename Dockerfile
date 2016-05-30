FROM python:3-onbuild
MAINTAINER Maurits van der Vijgh <mauritsvdvijgh@gmail.com>

RUN ["pip3", "install", "-e", "."]

ENTRYPOINT ["python3", "-u", "stakemachine/__main__.py"]
CMD ["run"]
