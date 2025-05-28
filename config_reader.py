from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    # Желательно вместо str использовать SecretStr
    # для конфиденциальных данных, например, токена бота
    bot_token: SecretStr
    admins: SecretStr

    # SmartProxy settings
    smartproxy_username: SecretStr
    smartproxy_password: SecretStr
    smartproxy_endpoint: str = "dc.decodo.com"
    smartproxy_port: str = "10000"

    # Начиная со второй версии pydantic, настройки класса настроек задаются
    # через model_config
    # В данном случае будет использоваться файла .env, который будет прочитан
    # с кодировкой UTF-8
    model_config = SettingsConfigDict(env_file='.venv/.env', env_file_encoding='utf-8')


# При импорте файла сразу создастся
# и провалидируется объект конфига,
# который можно далее импортировать из разных мест
config = Settings()
