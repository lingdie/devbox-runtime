#!/bin/bash

DOCKERFILE=$1
echo "DOCKERFILE: $DOCKERFILE"
TMP_DOCKERFILE="${DOCKERFILE}tmp"
cp "$DOCKERFILE" "$TMP_DOCKERFILE"

sed -i '$i\
COPY /OS/debian-ssh/debian.sources /etc/apt/sources.list.d/debian.sources' "$TMP_DOCKERFILE"

sed -i '$i\
RUN npm config set registry http://mirrors.cloud.tencent.com/npm/' "$TMP_DOCKERFILE"