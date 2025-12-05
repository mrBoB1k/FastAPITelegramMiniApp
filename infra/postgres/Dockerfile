FROM postgres:15-alpine

# Копируем скрипты инициализации
COPY init.sql /docker-entrypoint-initdb.d/
COPY *.sh /docker-entrypoint-initdb.d/

# Настройки (можно задать через environment)
ENV DB_NAME=myapp_db
ENV DB_USER=myapp_user
ENV DB_PASSWORD=secure_password

EXPOSE 5432