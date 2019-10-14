#!/bin/bash
xhost +local:root
nvidia-docker run -it \
    --name="tynguyen_torch_darts_docker"\
    -p 0.0.0.0:9009:9009\
    --privileged \
    --env="DISPLAY=$DISPLAY" \
    --env="QT_X11_NO_MITSHM=1" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume="$HOME/github_darts:/root/github_darts:rw" \
    --volume="$HOME/bags:/root/bags:rw" \
    --ipc=host tynguyen/dgx1_ubuntu18_cuda9_pytorch3:latest \
    bash
    #--ipc=host nvcr.io/nvidia/tensorflow:18.07-py2 \
    #--name="tynguyen_pytorch_docker" \
