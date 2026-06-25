# 🐟 Manjubinha Analises

Automação de análises de FIIs e Ações para o site [Manjubinha Investidor](https://manjubinhainvestidor.wordpress.com).

## Como funciona

- **2x por semana** (terça e sexta, 08h BRT) o script roda automaticamente
- Busca documentos novos nos sites de RI dos 60 ativos monitorados
- Analisa cada documento com a API do Claude (Sonnet)
- Publica o post no WordPress.com no padrão estabelecido
- Atualiza o `ranking.json` com o link do novo post
- Na **primeira execução**, busca todos os documentos de junho/2026 (retroativo)

## Arquivos

| Arquivo | Função |
|---|---|
| `analises.py` | Script principal de análise e publicação |
| `config.json` | 60 ativos com URLs de RI e dados de gestora |
| `ranking.json` | Notas dos 4 fatores + links dos posts publicados |
| `ranking.html` | Tabela interativa do ranking (GitHub Pages) |
| `controle_docs.json` | Histórico de documentos já processados |
| `requirements.txt` | Dependências Python |
| `.github/workflows/schedule.yml` | Agendamento automático |

## Configuração inicial (fazer uma única vez)

### 1. Criar os Secrets no GitHub

Acesse: `github.com/diakofart/manjubinha-analises` → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Adicione os 3 secrets abaixo:

| Nome | Valor | Como obter |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `WP_USER` | seu usuário WP | Seu login do WordPress.com |
| `WP_APP_PASS` | senha de app WP | WordPress.com → Perfil → Segurança → Senhas de aplicativo |

### 2. Ativar GitHub Pages

Acesse: **Settings** → **Pages** → Source: `main` branch → pasta `/` (root)

O ranking ficará disponível em:
`https://diakofart.github.io/manjubinha-analises/ranking.html`

### 3. Embedar o ranking no WordPress

No WordPress.com, crie um bloco HTML com:
```html
<iframe 
  src="https://diakofart.github.io/manjubinha-analises/ranking.html"
  width="100%" 
  height="700" 
  frameborder="0"
  scrolling="auto">
</iframe>
```

### 4. Rodar retroativo manualmente (primeira vez)

Acesse: **Actions** → **Manjubinha — Análises Automáticas** → **Run workflow**

Isso vai buscar todos os documentos de junho/2026 e publicar as análises.

## Atualização do ranking

As notas dos 4 fatores são atualizadas:
- **FIIs**: mensalmente (junto com a análise do relatório mensal)
- **Ações**: trimestralmente (junto com o resultado trimestral)

Para atualizar manualmente, edite o `ranking.json` diretamente no GitHub.

## Custo estimado

| Item | Custo |
|---|---|
| GitHub Actions | Gratuito |
| APIs B3/CVM | Gratuito |
| Claude Sonnet (~40 análises/mês) | ~R$ 12/mês |
| WordPress.com Personal | Já pago |
| **Total extra** | **~R$ 12/mês** |
