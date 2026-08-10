"""Exceções compartilhadas do modelo de acesso cross-project (ADR-006).

Vivem em core/ porque são reusadas por qualquer domínio que consulte um
projeto BigQuery alvo informado pelo usuário (catalog hoje; freshness e
profiling depois), não são específicas do domínio catalog.
"""


class ProjectAccessDeniedError(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Acesso negado ao projeto '{project_id}'.")


class ProjectNotFoundError(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Projeto '{project_id}' não encontrado ou não existe.")


class DatasetNotFoundError(Exception):
    def __init__(self, project_id: str, dataset_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        super().__init__(f"Dataset '{dataset_id}' não encontrado no projeto '{project_id}'.")


class TableNotFoundError(Exception):
    def __init__(self, project_id: str, dataset_id: str, table_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        super().__init__(f"Tabela '{table_id}' não encontrada em '{project_id}.{dataset_id}'.")
