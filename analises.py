"""
Manjubinha Investidor — Análises Automáticas
Usa Claude Haiku (Anthropic) para analisar e publicar no WordPress.

Controle de cota:
  - Modelo: claude-haiku-4-5 (~$0.80/MTok input, $4/MTok output)
  - ~1.000 tokens entrada + ~1.200 saída por ativo = ~2.200 tok/ativo
  - 60 ativos x 2.200 = ~132.000 tokens por execução
  - 2x/semana x 4 semanas = ~1.05M tokens/mês  -> dentro da cota
  - Sleep de 3s entre chamadas (limite: 50 RPM no Haiku)
"""

import os, json, requests, time, base64
from datetime import datetime, timedelta
from pathlib import Path

# -- Config -------------------------------------------------------------------
WP_URL      = "https://manjubinhainvestidor.com.br"
WP_USER     = os.environ["WP_USER"]
WP_PASS     = os.environ["WP_APP_PASS"]
CLAUDE_KEY  = os.environ["ANTHROPIC_API_KEY"]

WP_API      = f"{WP_URL}/wp-json/wp/v2"
_cred       = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
WP_HEADERS  = {"Authorization": f"Basic {_cred}"}

CLAUDE_URL  = "https://api.anthropic.com/v1/messages"
CLAUDE_HEADERS = {
    "x-api-key": CLAUDE_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}
CLAUDE_MODEL   = "claude-haiku-4-5"
MAX_TOKENS_OUT = 1200

CONTROLE    = Path("controle_docs.json")
CAT_FIIS    = None
CAT_ACOES   = None

MES_ATUAL   = datetime.today().strftime("%B de %Y")
MES_KEY     = datetime.today().strftime("%m-%Y")

ICON_FII    = "\U0001f4e6"
ICON_ACAO   = "\U0001f4c8"
ICON_PEIXE  = "\U0001f41f"
ICON_PASTA  = "\U0001f4c2"
ICON_CAL    = "\U0001f4c5"
ICON_ROBO   = "\U0001f916"
ICON_MEMO   = "\U0001f4dd"

# -- Prompts ------------------------------------------------------------------

PROMPT_FII = """Você é analista do Manjubinha Investidor. Pesquise o relatório mensal mais recente do FII {ticker} ({nome}) publicado em {mes} no site {ri_url} e escreva uma análise em HTML WordPress.

Use EXATAMENTE esta estrutura HTML (sem markdown, sem backticks, apenas HTML puro):

<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:heading {{"level":4}} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">Relatório Mensal — {mes}</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Publicado em: {mes} — <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial do fundo ({gestora}) ↗</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Tipo: {tipo} — Gestora: {gestora}</p><!-- /wp:paragraph --></div><!-- /wp:group -->
<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">💬 O que esse fundo faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[DESCRICAO]</p><!-- /wp:paragraph -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>DY mensal: X%</strong> — [explicacao]</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>P/VP: X,XX</strong> — [explicacao]</p><!-- /wp:paragraph -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🎯 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[ANALISE_DY]</p><!-- /wp:paragraph -->
<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[PONTOS]</p><!-- /wp:paragraph -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[ACOMPANHAMENTO]</p><!-- /wp:paragraph -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[BOA_NOTICIA]</p><!-- /wp:paragraph -->
<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[SIM/NAO + explicacao curta]</p><!-- /wp:paragraph -->
<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: [SIM/NEUTRO/NAO]</strong><br>[explicacao]</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização: [SIM/NEUTRO/NAO]</strong><br>[explicacao]</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>📌 [Conclusao em 2 frases]</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras: linguagem simples, máximo 500 palavras, números reais, sem texto fora do HTML."""

PROMPT_ACAO = """Você é analista do Manjubinha Investidor. Pesquise o resultado trimestral mais recente da empresa {ticker} ({nome}) publicado em 2026 no site {ri_url} e escreva uma análise em HTML WordPress.

Use EXATAMENTE esta estrutura HTML (sem markdown, sem backticks, apenas HTML puro):

<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:heading {{"level":4}} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">Resultado Trimestral — [TRIMESTRE]</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Publicado em: [DATA] — <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial de RI ({nome}) ↗</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Setor: {setor} — Empresa: {nome} S.A.</p><!-- /wp:paragraph --></div><!-- /wp:group -->
<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">💬 O que essa empresa faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[DESCRICAO]</p><!-- /wp:paragraph -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>P/L: X,X</strong> — [explicacao]</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Dividend Yield anual: X%</strong> — [explicacao]</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Dívida/EBITDA: X,Xx</strong> — [explicacao]</p><!-- /wp:paragraph -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🎯 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[ANALISE_DY]</p><!-- /wp:paragraph -->
<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[PONTOS]</p><!-- /wp:paragraph -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[ACOMPANHAMENTO]</p><!-- /wp:paragraph -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[BOA_NOTICIA]</p><!-- /wp:paragraph -->
<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>[SIM/NAO + explicacao curta]</p><!-- /wp:paragraph -->
<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: [SIM/NEUTRO/NAO]</strong><br>[explicacao]</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização: [SIM/NEUTRO/NAO]</strong><br>[explicacao]</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>📌 [Conclusao em 2 frases]</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras: linguagem simples, máximo 500 palavras, números reais, sem texto fora do HTML."""

# -- Helpers ------------------------------------------------------------------

def carregar(path, default):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default

def salvar(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

def chamar_claude(prompt):
    time.sleep(3)
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": MAX_TOKENS_OUT,
        "messages": [{"role": "user", "content": prompt}],
    }
    for tentativa in range(4):
        try:
            r = requests.post(CLAUDE_URL, headers=CLAUDE_HEADERS, json=payload, timeout=60)
            if r.status_code == 200:
                return r.json()["content"][0]["text"].strip()
            elif r.status_code == 429:
                wait = 30 * (tentativa + 1)
                print("  Rate limit -- " + str(wait) + "s (tentativa " + str(tentativa+1) + "/4)")
                time.sleep(wait)
            elif r.status_code == 529:
                print("  Overload -- 60s (tentativa " + str(tentativa+1) + "/4)")
                time.sleep(60)
            else:
                print("  Claude " + str(r.status_code) + ": " + r.text[:200])
                return None
        except requests.exceptions.Timeout:
            print("  Timeout -- tentativa " + str(tentativa+1) + "/4")
            time.sleep(15)
    print("  Claude: 4 tentativas falharam.")
    return None

def get_or_create_category(slug, name):
    r = requests.get(f"{WP_API}/categories", headers=WP_HEADERS, params={"slug": slug})
    cats = r.json()
    if isinstance(cats, list) and cats:
        return cats[0]["id"]
    r = requests.post(f"{WP_API}/categories", headers=WP_HEADERS, json={"name": name, "slug": slug})
    return r.json().get("id")

def get_or_create_tag(ticker):
    r = requests.get(f"{WP_API}/tags", headers=WP_HEADERS, params={"search": ticker})
    tags = r.json()
    if isinstance(tags, list) and tags:
        return tags[0]["id"]
    nova = requests.post(f"{WP_API}/tags", headers=WP_HEADERS, json={"name": ticker}).json()
    return nova.get("id")

def publicar(titulo, conteudo, categoria, ticker):
    tag_id = get_or_create_tag(ticker)
    r = requests.post(f"{WP_API}/posts", headers=WP_HEADERS, json={
        "title":      titulo,
        "content":    conteudo,
        "status":     "publish",
        "categories": [categoria],
        "tags":       [tag_id] if tag_id else [],
    })
    if r.status_code in (200, 201):
        url = r.json()["link"]
        print("  OK: " + url)
        return url
    print("  WP erro " + str(r.status_code) + ": " + r.text[:300])
    return None

def atualizar_ranking(ticker, url, tipo):
    ranking = carregar("ranking.json", {})
    lista = ranking.get("fiis" if tipo == "fii" else "acoes", [])
    for item in lista:
        if item["ticker"] == ticker:
            item["post_url"] = url
            break
    ranking["ultima_atualizacao"] = datetime.today().strftime("%Y-%m-%d")
    salvar("ranking.json", ranking)

# -- Processamento ------------------------------------------------------------

def processar(lista, controle, mes_key, mes_nome, tipo):
    label = "FIIs" if tipo == "fii" else "Acoes"
    print("")
    print("Processando " + label + "...")
    for ativo in lista:
        t = ativo["ticker"]
        key = t + "_" + mes_key
        if key in controle and controle[key].get("status") == "ok":
            print("  " + t + ": ja publicado.")
            continue
        print("")
        print("  -> " + t + " (" + ativo["nome"] + ")")
        if tipo == "fii":
            prompt = PROMPT_FII.format(
                ticker=t, nome=ativo["nome"],
                ri_url=ativo["ri_url"],
                tipo=ativo.get("tipo", ""),
                gestora=ativo.get("gestora", ""),
                mes=mes_nome,
            )
        else:
            prompt = PROMPT_ACAO.format(
                ticker=t, nome=ativo["nome"],
                ri_url=ativo["ri_url"],
                setor=ativo.get("setor", ""),
            )
        print("  Analisando com Claude Haiku...")
        analise = chamar_claude(prompt)
        if not analise:
            controle[key] = {"status": "erro_claude"}
            salvar(CONTROLE, controle)
            continue
        if tipo == "fii":
            titulo = t + " -- " + ativo["nome"] + " | Relatorio " + mes_nome
        else:
            titulo = t + " -- " + ativo["nome"] + " | Resultado 2026"
        cat = CAT_FIIS if tipo == "fii" else CAT_ACOES
        print("  Publicando...")
        url = publicar(titulo, analise, cat, t)
        if url:
            atualizar_ranking(t, url, tipo)
            controle[key] = {"status": "ok", "url": url}
        else:
            controle[key] = {"status": "erro_wp"}
        salvar(CONTROLE, controle)

# -- Main ---------------------------------------------------------------------

def main():
    print("Manjubinha -- " + datetime.today().strftime("%Y-%m-%d %H:%M UTC"))
    config   = carregar("config.json", {})
    controle = carregar(CONTROLE, {})
    global CAT_FIIS, CAT_ACOES
    CAT_FIIS  = get_or_create_category("analises-fiis",    "FIIs | Analises")
    CAT_ACOES = get_or_create_category("documentos-acoes", "Acoes | Analises")
    print("  FIIs: " + str(CAT_FIIS) + " | Acoes: " + str(CAT_ACOES))
    print("  Mes: " + MES_ATUAL)
    processar(config.get("fiis",  []), controle, MES_KEY, MES_ATUAL, "fii")
    processar(config.get("acoes", []), controle, MES_KEY, MES_ATUAL, "acao")
    print("")
    print("Concluido!")

if __name__ == "__main__":
    main()
