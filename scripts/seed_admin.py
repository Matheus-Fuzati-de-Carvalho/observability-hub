#!/usr/bin/env python3
"""Bootstrap do primeiro administrador do Hub — roda uma vez por ambiente
(dev, depois prod), antes ou logo após o primeiro deploy do backend com
o gate de ACL ativo (domains/admin, core/auth.py::require_admin /
require_project_access). Sem isso, a coleção hub_users fica vazia e
ninguém consegue abrir /admin pra criar o primeiro registro — nem
require_admin nem require_project_access liberam nada sem doc existente
(fail closed por design, ver docs/specs/admin.md, "Casos de borda").

Usa as credenciais do OPERADOR (`gcloud auth application-default login`),
não a service account de runtime do Cloud Run — este script roda
localmente, fora do Hub, e não duplica lógica do backend de propósito
(fica independente da estrutura de pacote de apps/backend).

Uso (a partir de apps/backend, pra usar o venv/uv.lock já resolvido):
    cd apps/backend
    uv run python ../../scripts/seed_admin.py \\
        --project observability-hub-dev --email primeiro-admin@dp6.com.br

Roda primeiro em dev, valida o fluxo ponta a ponta (login -> /admin
abre -> consegue gerenciar outros usuários), só depois em prod.
"""

import argparse
from datetime import UTC, datetime

from google.cloud import firestore


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Projeto GCP onde o Hub roda (observability-hub-dev ou -prod)",
    )
    parser.add_argument("--email", required=True, help="E-mail do primeiro administrador")
    args = parser.parse_args()

    email = args.email.strip().lower()
    client = firestore.Client(project=args.project)
    now = datetime.now(UTC)

    doc_ref = client.collection("hub_users").document(email)
    existing = doc_ref.get()
    data = {
        "email": email,
        "is_admin": True,
        "allowed_projects": ["*"],
        "created_at": existing.to_dict()["created_at"] if existing.exists else now,
        "updated_at": now,
        "updated_by": "scripts/seed_admin.py",
    }
    doc_ref.set(data)

    print(f"OK — {email} agora é administrador do Hub em {args.project} (hub_users/{email}).")


if __name__ == "__main__":
    main()
