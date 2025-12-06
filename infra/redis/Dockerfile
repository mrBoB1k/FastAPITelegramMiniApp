FROM redis:7-alpine

# Отключаем protected-mode для доступа извне
# Или оставляем для безопасности в продакшене
CMD ["redis-server", "--bind", "0.0.0.0"]