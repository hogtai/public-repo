FROM ubuntu
RUN apt-get update && apt-get install -y git python3-pip
RUN git clone <repo1-url #3>
WORKDIR /<repo1-dir #3>
RUN pip3 install -r requirements.txt
CMD ["python3", "app.py"]
