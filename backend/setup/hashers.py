from django.contrib.auth.hashers import BCryptSHA256PasswordHasher


class BCrypt12PasswordHasher(BCryptSHA256PasswordHasher):
    """
    Hasher bcrypt com custo fixo 12 (Arq. §8).
    O BCryptSHA256PasswordHasher padrão usa rounds=12 por default,
    mas definimos explicitamente para garantir mesmo que o default mude.
    """
    rounds = 12