FROM ghcr.io/labring-actions/devbox/node.js-20:8c965d

RUN cd /home/sealos/project && \
rm -rf ./*

COPY /Framework/vue/v3.4.29/project /home/sealos/project
RUN chown -R sealos:sealos /home/sealos/project && \
chmod -R u+rw /home/sealos/project && \
chmod -R +x /home/sealos/project/entrypoint.sh

USER sealos
RUN cd /home/sealos/project && \
npm install && \
npm run build
 
USER root
RUN mkdir /home/sealos/.sealos