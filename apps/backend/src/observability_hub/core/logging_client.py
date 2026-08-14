"""Client compartilhado do Cloud Logging — mesmo padrão de
core/bigquery.py::get_client() (client cacheado por processo via
lru_cache). Usado por domains/lineage (audit logs de BigQuery) e, no
futuro, por domains/access (mapa de acesso), que lê a mesma fonte de
audit logs.

`_use_grpc=False` é obrigatório: o audit log de job do BigQuery vem com
`protoPayload` duplamente aninhado em `Any` (AuditLog -> serviceData ->
AuditData, formato legado `google.cloud.bigquery.logging.v1.AuditData`).
O transporte gRPC padrão do client Python só decodifica `Any` pra dict
via `MessageToDict` usando o descriptor pool local do processo — e não
existe pacote Python publicado com o `.proto`/pb2 desse tipo específico
da BigQueryAuditData, então a decodificação sempre falha e
`entry.payload` volta como `google.protobuf.any_pb2.Any` cru (bytes),
nunca como dict, silenciosamente descartado por
`domains/lineage/repository._parse_entry`. O transporte REST não tem
esse problema — o payload já chega pronto como JSON/dict do servidor
(mesmo formato que `gcloud logging read --format=json` mostra),
confirmado ao vivo contra observability-hub-dev em 2026-08-14.
"""

from functools import lru_cache

from google.cloud import logging as cloud_logging


@lru_cache
def get_logging_client() -> cloud_logging.Client:
    return cloud_logging.Client(_use_grpc=False)
