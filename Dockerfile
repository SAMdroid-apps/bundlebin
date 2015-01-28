FROM debian

RUN apt-get update
RUN apt-get install git python-pip sqlite3 -y --fix-missing

RUN git clone http://github.com/samdroid-apps/bundlebin /bundlebin
RUN pip install -r /bundlebin/requirments.txt

RUN mkdir -p /data/uploads
RUN sqlite3 /data/data.db "create table aTable(field1 int); drop table aTable;"
ENV BUNDLEBIN_SETTINGS /bundlebin/docker_config.py
VOLUME /data

EXPOSE 5000
CMD python /bundlebin/main.py
