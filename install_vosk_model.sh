#!/bin/bash
cd /tmp
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
sudo mkdir -p /usr/share/vosk-models
sudo mv vosk-model-small-en-us-0.15 /usr/share/vosk-models/small-en-us
sudo chmod -R a+rX /usr/share/vosk-models/small-en-us
