from werkzeug.security import check_password_hash


def verify_password(db_hash: str, pwd: str) -> bool:
    if db_hash.startswith("scrypt:") or db_hash.startswith("pbkdf2:"):
        return check_password_hash(db_hash, pwd)

    import hashlib

    return hashlib.sha256(pwd.encode("utf-8")).hexdigest() == db_hash
