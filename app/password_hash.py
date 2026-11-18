from getpass import getpass

from argon2 import PasswordHasher


def main() -> None:
    password = getpass("Пароль администратора: ")
    confirmation = getpass("Повторите пароль: ")
    if not password:
        raise SystemExit("Пароль не может быть пустым.")
    if password != confirmation:
        raise SystemExit("Пароли не совпадают.")
    print(PasswordHasher().hash(password))


if __name__ == "__main__":
    main()
