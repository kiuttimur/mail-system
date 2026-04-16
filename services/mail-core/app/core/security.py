"""Минимальные утилиты хеширования и проверки паролей без внешних библиотек."""

from __future__ import annotations

import hashlib
import hmac
import secrets

PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    # Формат хеша: scheme$iterations$salt$derived_key
    salt = secrets.token_hex(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    )
    return f"{PASSWORD_HASH_SCHEME}${PASSWORD_HASH_ITERATIONS}${salt}${derived_key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    # На повреждённом или старом формате не падаем, а просто считаем пароль неверным.
    try:
        scheme, iterations, salt, expected_hash = password_hash.split("$", 3)
        iterations_value = int(iterations)
    except ValueError:
        return False

    if scheme != PASSWORD_HASH_SCHEME:
        return False

    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations_value,
    )
    return hmac.compare_digest(derived_key.hex(), expected_hash)
