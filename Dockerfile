#Tensorflow v2.3.1 is needed for sleap v1.1.3
#FROM tensorflow/tensorflow:2.4.1-gpu-jupyter
FROM nvcr.io/nvidia/tensorflow:21.03-tf2-py3

# Needed for sleap
RUN apt-get update && apt-get install -y libgl1

# Not needed, but can be useful
RUN apt-get update && apt-get install -y wget tree

# download test dataset https://sleap.ai/notebooks/Training_and_inference_on_an_example_dataset.html
RUN wget -O /root/dataset.zip https://github.com/murthylab/sleap-datasets/releases/download/dm-courtship-v1/drosophila-melanogaster-courtship.zip && mkdir /root/dataset && unzip /root/dataset.zip -d /root/dataset && rm /root/dataset.zip

# get sleap
COPY . /root/Repos/sleap/
#RUN pip install -r /root/Repos/sleap/requirements.txt
RUN python3 -m pip install /root/Repos/sleap/

WORKDIR /root

#Instructions:
#cd in folder with this file and then build the docker image with
#   docker build -t sleap .
#then run the image and open interactive shell with:
#   docker run --gpus all -it --rm sleap /bin/bash
# run this command in the container to test gpu:
#   sleap-train baseline.centroid.json "dataset/drosophila-melanogaster-courtship/courtship_labels.slp" --run_name "courtship.centroid" --video-paths "dataset/drosophila-melanogaster-courtship/20190128_113421.mp4"

