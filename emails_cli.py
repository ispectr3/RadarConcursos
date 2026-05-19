"""Gerencia assinantes de e-mail no SQLite (tabela email_subscribers)."""

from __future__ import annotations

import argparse
import sys

from storage import (
    add_email_subscriber,
    init_db,
    list_email_subscribers,
    remove_email_subscriber,
    set_subscriber_active,
)


def main() -> None:
    init_db()
    p = argparse.ArgumentParser(description="Assinantes de alertas por e-mail")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="Adiciona ou reativa um e-mail")
    a.add_argument("email")

    sub.add_parser("list", help="Lista cadastrados")

    r = sub.add_parser("remove", help="Remove do cadastro")
    r.add_argument("email")

    d = sub.add_parser("disable", help="Desativa sem apagar")
    d.add_argument("email")

    e = sub.add_parser("enable", help="Reativa")
    e.add_argument("email")

    args = p.parse_args()
    if args.cmd == "add":
        if add_email_subscriber(args.email):
            print("OK:", args.email.strip().lower())
        else:
            print("E-mail inválido.", file=sys.stderr)
            sys.exit(1)
    elif args.cmd == "list":
        rows = list_email_subscribers()
        if not rows:
            print("(nenhum — use: python emails_cli.py add seu@email.com)")
            return
        for email, active, created in rows:
            flag = "ativo" if active else "desligado"
            print(f"{email}\t{flag}\t{created}")
    elif args.cmd == "remove":
        remove_email_subscriber(args.email)
        print("Removido:", args.email.strip().lower())
    elif args.cmd == "disable":
        set_subscriber_active(args.email, False)
        print("Desativado:", args.email.strip().lower())
    elif args.cmd == "enable":
        set_subscriber_active(args.email, True)
        print("Ativado:", args.email.strip().lower())


if __name__ == "__main__":
    main()
