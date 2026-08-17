# Observability Hub — Liberação de Acesso

**Como autorizar a leitura do seu projeto Google Cloud**

---

## Sobre este manual

Este documento orienta a liberação de **acesso de leitura** ao seu
projeto Google Cloud para que o Observability Hub possa analisá-lo —
catálogo de dados, monitoramento de atualização e qualidade das tabelas.

**Quem deve executar:** um responsável técnico com permissão para
gerenciar papéis de IAM no projeto (papel de *Owner* ou *IAM Admin*).

**Tempo estimado:** 10 a 15 minutos.

---

## O que este processo faz (e o que não faz)

- **Acesso só de leitura.** Nenhuma permissão de escrita, alteração ou
  exclusão é concedida em nenhum momento.
- **Nada é instalado no seu projeto.** Sem agente, sem máquina virtual,
  sem serviço novo rodando do seu lado — a leitura acontece de fora,
  via API do Google Cloud.
- **Acesso escopado e nomeado.** As permissões vão para uma conta de
  serviço específica, que informamos abaixo — nada é concedido a
  "qualquer usuário" ou de forma ampla.
- **Revogável a qualquer momento.** Basta remover as permissões
  concedidas (comando de revogação ao final deste manual) para encerrar
  o acesso, sem qualquer efeito colateral no seu projeto.
- **Você confirma cada permissão antes de conceder.** Os comandos abaixo
  são explícitos — nada é feito de forma automática ou oculta.

---

## Passo 1 — Confirmar a conta de serviço a autorizar

Autorize a conta de serviço que constará na proposta/contrato:

```
{conta-de-servico}@{projeto-do-hub}.iam.gserviceaccount.com
```

Se o mesmo projeto for consultado tanto em ambiente de homologação
quanto de produção, o mesmo processo se repete para as duas contas.

---

## Passo 2 — Habilitar as APIs necessárias

```bash
gcloud services enable bigquery.googleapis.com logging.googleapis.com \
  --project={SEU_PROJETO}
```

---

## Passo 3 — Conceder as permissões de leitura

```bash
CONTA_DE_SERVICO="{conta-de-servico}@{projeto-do-hub}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding {SEU_PROJETO} \
  --member="serviceAccount:${CONTA_DE_SERVICO}" --role="roles/bigquery.metadataViewer"

gcloud projects add-iam-policy-binding {SEU_PROJETO} \
  --member="serviceAccount:${CONTA_DE_SERVICO}" --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding {SEU_PROJETO} \
  --member="serviceAccount:${CONTA_DE_SERVICO}" --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding {SEU_PROJETO} \
  --member="serviceAccount:${CONTA_DE_SERVICO}" --role="roles/logging.viewer"

gcloud projects add-iam-policy-binding {SEU_PROJETO} \
  --member="serviceAccount:${CONTA_DE_SERVICO}" --role="roles/logging.privateLogViewer"
```

| Permissão | Para que serve |
|---|---|
| `bigquery.metadataViewer` | Ler a estrutura dos dados — datasets, tabelas, colunas |
| `bigquery.jobUser` | Executar as consultas necessárias para ler essa estrutura |
| `bigquery.dataViewer` | Analisar qualidade dos dados (amostragem, duplicidade, valores nulos) |
| `logging.viewer` | Consultar o histórico de uso das tabelas |
| `logging.privateLogViewer` | Complementa a anterior — sem ela, o histórico de uso vem sempre vazio (ver nota abaixo) |

> **Atenção:** as duas últimas permissões precisam ser concedidas
> **juntas**. Só com `logging.viewer`, nada falha — mas o histórico de
> uso das tabelas simplesmente nunca aparece, sem nenhum aviso de erro.

Todos os comandos são seguros para executar mais de uma vez.

---

## Passo 4 — Habilitar o histórico de uso (opcional)

Necessário apenas se for utilizado o rastreamento de linhagem de dados
ou o mapa de acessos. Sem esta etapa, essas duas funcionalidades
simplesmente não mostram dado nenhum — as demais funcionam normalmente.

**Pelo Console do Google Cloud:** IAM e Administrador → Auditoria →
localizar "BigQuery API" → marcar "Leitura de dados" e "Gravação de
dados" → Salvar.

**Por linha de comando**, sempre preservando as configurações já
existentes:

```bash
gcloud projects get-iam-policy {SEU_PROJETO} --format=json > politica.json
# adicionar (sem remover o que já existe) o bloco abaixo em "auditConfigs"
```

```json
{
  "auditConfigs": [
    {
      "service": "bigquery.googleapis.com",
      "auditLogConfigs": [
        { "logType": "DATA_READ" },
        { "logType": "DATA_WRITE" }
      ]
    }
  ]
}
```

```bash
gcloud projects set-iam-policy {SEU_PROJETO} politica.json
```

---

## Passo 5 — Confirmar

```bash
gcloud projects get-iam-policy {SEU_PROJETO} \
  --flatten="bindings[].members" \
  --filter="bindings.members:{conta-de-servico}@{projeto-do-hub}.iam.gserviceaccount.com" \
  --format="table(bindings.role)"
```

O resultado deve listar as cinco permissões do Passo 3. A partir daqui,
o acesso está liberado e pronto para uso.

---

## Checklist

```
[ ] APIs habilitadas (BigQuery, Cloud Logging)
[ ] 5 permissões de leitura concedidas à conta de serviço informada
[ ] Histórico de uso habilitado — apenas se for usar linhagem/mapa de acessos
[ ] Concessão confirmada por linha de comando
```

---

## Revogar o acesso

Para encerrar o acesso a qualquer momento, remova as mesmas permissões
concedidas — sem efeito colateral no restante do projeto:

```bash
CONTA_DE_SERVICO="{conta-de-servico}@{projeto-do-hub}.iam.gserviceaccount.com"

for PAPEL in roles/bigquery.metadataViewer roles/bigquery.jobUser \
             roles/bigquery.dataViewer roles/logging.viewer \
             roles/logging.privateLogViewer; do
  gcloud projects remove-iam-policy-binding {SEU_PROJETO} \
    --member="serviceAccount:${CONTA_DE_SERVICO}" --role="${PAPEL}"
done
```

---

## Perguntas frequentes

**O Hub grava ou altera algo no meu projeto?** Não. Todas as permissões
concedidas são exclusivamente de leitura.

**Isso dá acesso ao faturamento (billing) do meu projeto?** Não —
nenhuma permissão de billing é solicitada.

**Alguém consegue ver meus dados sem eu saber?** O acesso é técnico
(a nível de infraestrutura); quem efetivamente consulta seus dados
pelo Hub também precisa estar previamente autorizado do lado da
plataforma — é uma segunda camada de controle, independente desta.

**Isso é permanente?** Não — pode ser revogado a qualquer momento, ver
seção "Revogar o acesso" acima.

---

Para qualquer dúvida durante a execução, entre em contato com nossa
equipe em **{e-mail ou canal de suporte}**.
