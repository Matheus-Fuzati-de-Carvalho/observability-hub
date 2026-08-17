# Frontend Design Skill — Observability Hub

Identidade visual baseada no brand dp6 (part of the brandtech group).
Referência de produto: Metabase — denso, funcional, orientado a dados.
Filosofia: minimalismo com personalidade. Menos decoração, mais clareza.

---

## Paleta de cores

```css
/* Cores primárias dp6 */
--color-primary:       #FFB302;   /* amarelo dp6 — ações, destaques, CTAs */
--color-bg-dark:       #1D1D1B;   /* fundo escuro principal */
--color-bg-surface:    #2A2A28;   /* superfícies elevadas (cards, sidebar) */
--color-bg-muted:      #3A3A38;   /* hover states, bordas sutis */
--color-text-primary:  #FFFFFF;   /* texto principal no dark */
--color-text-muted:    #8F96A1;   /* texto secundário, labels — >=4.5:1 (WCAG AA) contra --color-bg-dark/-surface; #5B626C original tinha ~2.74:1, quase ilegível */
--color-text-inverse:  #1D1D1B;   /* texto sobre fundo amarelo */

/* Cores de apoio para gráficos e status */
--color-status-ok:      #34D399;  /* verde — dentro do SLA */
--color-status-warn:    #FFB302;  /* amarelo — alerta */
--color-status-error:   #E53E3E;  /* vermelho — fora do SLA / crítico */
--color-status-info:    #63B3ED;  /* azul — informação */

/* Acento secundário */
--color-accent-blue:    #1A365D;
--color-accent-purple:  #6B46C1;
--color-accent-green:   #059669;
```

---

## Tipografia

```css
/* Fonte principal — Ubuntu (Google Fonts) */
@import url('https://fonts.googleapis.com/css2?family=Ubuntu:wght@300;400;700&display=swap');

--font-sans: 'Ubuntu', 'Verdana', system-ui, sans-serif;

/* Escala tipográfica */
--text-xs:   0.75rem;   /* 12px — labels de tabela, metadados */
--text-sm:   0.875rem;  /* 14px — corpo de tabela, valores */
--text-base: 1rem;      /* 16px — texto corrido */
--text-lg:   1.125rem;  /* 18px — subtítulos de seção */
--text-xl:   1.25rem;   /* 20px — títulos de card */
--text-2xl:  1.5rem;    /* 24px — títulos de página */
--text-3xl:  1.875rem;  /* 30px — KPIs grandes */
```

---

## Layout e espaçamento

O layout é **denso como Metabase** — máximo de informação na viewport sem scroll desnecessário.

```
┌─────────────────────────────────────────────────────────┐
│  Topbar: seletor de projeto + logo dp6          [240px] │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│ Sidebar  │  Área principal de conteúdo                  │
│ 240px    │  (catálogo, freshness, tabelas)              │
│          │                                              │
│ datasets │                                              │
│ listados │                                              │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

- Sidebar: `240px` fixa, fundo `#2A2A28`, lista de datasets clicáveis
- Topbar: `56px`, fundo `#1D1D1B`, linha amarela inferior `2px solid #FFB302`
- Conteúdo: padding `24px`, gap entre cards `16px`
- Cards: `border-radius: 8px`, fundo `#2A2A28`, sem sombras pesadas

---

## Elementos gráficos dp6

### Linha vertical amarela (divisor de identidade)
```css
.dp6-divider {
  width: 2px;
  background: #FFB302;
  height: 100%;
}
```
Usar como separador entre logo e título, ou como accent lateral em seções.

### Cards com borda amarela em hover
```css
.card {
  background: #2A2A28;
  border: 1px solid #3A3A38;
  border-radius: 8px;
  transition: border-color 0.15s;
}
.card:hover {
  border-color: #FFB302;
}
```

### Botão primário (CTA)
```css
.btn-primary {
  background: #FFB302;
  color: #1D1D1B;
  font-weight: 700;
  border-radius: 6px;
  padding: 8px 16px;
}
.btn-primary:hover {
  background: #E6A000;
}
```

### Botão secundário (outline)
```css
.btn-secondary {
  background: transparent;
  color: #FFB302;
  border: 1px solid #FFB302;
  border-radius: 6px;
  padding: 8px 16px;
}
```

---

## Componentes principais

### Topbar — seletor de projeto
```
┌─────────────────────────────────────────────────────────┐
│ ▌ dp6   │  GCP Project: [observability-hub-dev    ▾]   │
└─────────────────────────────────────────────────────────┘
```
- Logo dp6 à esquerda com linha vertical amarela divisora
- Input de projeto com ícone de busca, validação visual (verde = acessível, vermelho = sem acesso)
- Ao validar com sucesso: sidebar popula com os datasets do projeto

### Sidebar — lista de datasets
```
DATASETS DISPONÍVEIS
━━━━━━━━━━━━━━━━━━━
● RAW          [3 tabelas]
  TRUSTED      [2 tabelas]
  REFINED      [2 views]
```
- Item ativo: fundo `#FFB302`, texto `#1D1D1B`, font-weight 700
- Item inativo: texto `#FFFFFF`, hover fundo `#3A3A38`
- Ponto colorido de status SLA ao lado do nome (verde/amarelo/vermelho)

### Cards de resumo do dataset (KPI row)
```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  REGIÃO  │ │  TABELAS │ │  TAMANHO │ │   LINHAS │ │  FRESHNESS│
│    US    │ │    3     │ │  1.98 MB │ │  30.000  │ │  >1 mês  │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```
- 5 cards em row, flex-grow igual
- KPI numérico em `--text-3xl` bold, label em `--text-xs` muted uppercase
- Card de alerta (ex: SLA violado): borda `#E53E3E`

### Tabela de ativos
- Header: uppercase, `--text-xs`, `--color-text-muted`, border-bottom `#3A3A38`
- Linhas: hover fundo `#3A3A38`, cursor pointer
- Badge de tipo (TABLE / VIEW / EXTERNAL): pill com fundo `#3A3A38`, texto `--text-xs`
- Botão "Analisar": outline amarelo, só aparece no hover da linha
- Colunas: Nome/ID, Tipo, Qtd Colunas, Criação, Atualização, Linhas, Volume, Região

### SLA de atualização (freshness row)
```
Até 12h    12h a 24h   24h a 48h   48h a 7d    7d a 1m    >1 mês
   0           0           0           0           0          3
```
- 6 colunas em row, label `--text-xs` muted, valor `--text-xl` bold
- Valor > 0: colorido conforme status (verde → vermelho)
- Valor = 0: `--color-text-muted`

### Modal de profiling
- Overlay: `rgba(0,0,0,0.7)`, blur backdrop
- Modal: `max-width: 900px`, fundo `#2A2A28`, padding `32px`
- Header: "MÓDULO DE QUALIDADE" em `--text-xs` uppercase amarelo, tabela em `--text-lg`
- Linha de controles: Amostragem | Método Unicidade | Coluna de Data | Janela | [Estimar Custo] [Executar Profile]
- Seção de resultado SQL: fundo `#1D1D1B`, `font-family: monospace`, texto branco, botão "Copiar SQL"
- Tabela de resultados por coluna:
  - Completude: barra de progresso (verde se >80%, amarelo se 50-80%, vermelho se <50%)
  - Unicidade HLL: valor % em roxo se alta cardinalidade, laranja se baixa
  - Min/Max: texto muted

---

## Ícones

Usar `lucide-react` (já disponível no projeto). Ícones outline, tamanho padrão `16px` inline, `20px` em botões.

Mapeamento de domínios:
- Catálogo: `Database`
- Freshness: `Clock`
- Profiling: `BarChart2`
- FinOps: `DollarSign`
- Qualidade: `CheckCircle`
- Alerta: `AlertTriangle`
- Projeto GCP: `Cloud`

---

## Regras de UI — o que NÃO fazer

- Não usar gradientes — identidade dp6 é flat
- Não usar sombras pesadas (`box-shadow`) — bordas sutis são suficientes
- Não usar mais de 2 cores de destaque por tela
- Não centralizar texto em tabelas — sempre left-align exceto números (right-align)
- Não usar skeleton loaders elaborados — spinner simples em amarelo
- Não adicionar animações longas — transitions máximo `200ms`
- Não usar fontes além de Ubuntu/Verdana
- Não criar páginas separadas por domínio — tudo na mesma SPA com sidebar

---

## Modo claro (opcional, futuro)

O brand dp6 tem versão light (fundo branco, texto `#1D1D1B`). Não implementar no MVP — dark mode é o padrão. Quando implementar, inverter apenas `--color-bg-*` e `--color-text-*`, mantendo `#FFB302` como acento.

---

## Tailwind config (mapeamento das CSS vars)

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary:   '#FFB302',
        'bg-dark':    '#1D1D1B',
        'bg-surface': '#2A2A28',
        'bg-muted':   '#3A3A38',
        'text-muted': '#8F96A1',
        'status-ok':    '#34D399',
        'status-warn':  '#FFB302',
        'status-error': '#E53E3E',
        'status-info':  '#63B3ED',
      },
      fontFamily: {
        sans: ['Ubuntu', 'Verdana', 'system-ui', 'sans-serif'],
      },
    },
  },
}
```
