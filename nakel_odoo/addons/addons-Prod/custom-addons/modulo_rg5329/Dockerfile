FROM odoo:18.0

USER root
RUN apt-get update && apt-get install -y python3-dev libpq-dev gcc

USER odoo
COPY ./my_module /mnt/extra-addons/my_module
