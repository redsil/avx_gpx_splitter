FROM ubuntu:20.04

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get -y install python3 python3-flask python3-pip python3-geopy python3-simplejson python-is-python3 python3-regex
RUN apt-get -y install curl
RUN apt-get -y install git
RUN pip3 install typing
RUN pip3 install gpxpy
RUN git clone https://github.com/redsil/avx_gpx_splitter.git .

CMD ["./web_server.py","5766"]
EXPOSE 5766
EXPOSE 49002/udp

