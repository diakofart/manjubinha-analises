"""
Manjubinha Investidor - Analises Automaticas
Roda 4x por dia (a cada 6h). Processa 2 FIIs + 2 Acoes por rodada.
Ciclo semanal: cobre todos os 60 ativos em ~5 dias.
"""

import os, json, requests, time
from datetime import datetime
from pathlib import Path

# Config
WP_URL     = "https://manjubinhainvestidor.com.br"
WP_USER    = os.environ["WP_USER"]
WP_PASS    = os.environ["WP_APP_PASS"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

WP_API     = f"{WP_URL}/wp-json/wp/v2"
import base64
_cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
WP_HEADERS = {"Authorization": f"Basic {_cred}"}

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

CONTROLE   = Path("controle_docs.json")
POR_RODADA = 2  # 2 FIIs + 2 Acoes = 4 por rodada

PROMPT_FII = """Voce e analista do site Manjubinha Investidor. Pesquise informacoes recentes do FII {ticker} ({nome}) e escreva uma analise completa em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group"><!-- wp:heading {"level":4} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO - PERIODO</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Publicado em: DD/MM/AAAA - <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial do fundo ({gestora})</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Tipo: {tipo} - Gestora: {gestora}</p><!-- /wp:paragraph --></div><!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">O que esse fundo faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>DY mensal: X%</strong> - explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>P/VP: X,XX</strong> - explicacao curta.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Analise se o DY esta dentro do padrao. Se fundo de papel: Fundos de papel nao devem ser comprados com P/VP acima de 1,0.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Pontos de Atencao</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Boa Noticia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Sim ou Nao com explicacao direta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Foco em Renda: RESULTADO</strong><br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Foco em Valorizacao: RESULTADO</strong><br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>Conclusao em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras: linguagem simples, maximo 600 palavras, numeros reais, sem markdown extra."""

PROMPT_ACAO = """Voce e analista do site Manjubinha Investidor. Pesquise informacoes recentes da empresa {ticker} ({nome}) e escreva uma analise completa em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group"><!-- wp:heading {"level":4} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO - PERIODO</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Publicado em: DD/MM/AAAA - <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial de RI ({nome})</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Setor: {setor} - Empresa: {nome}</p><!-- /wp:paragraph --></div><!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">O que essa empresa faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Receita: R$ X bi</strong> - explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Lucro: R$ X bi</strong> - explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>DY anual: X%</strong> - explicacao curta.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>DY dentro do padrao historico ou inflado por extraordinarios?</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Pontos de Atencao</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Boa Noticia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Sim ou Nao com explicacao direta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Foco em Renda: RESULTADO</strong><br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Foco em Valorizacao: RESULTADO</strong><br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>Conclusao em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras: linguagem simples, maximo 600 palavras, numeros reais, sem markdown extra."""

def carregar(path, default):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default

def salvar(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

def semana_atual():
    hoje = datetime.today()
    return f"{hoje.year}-W{hoje.isocalendar()[1]:02d}"

def gemini(prompt):
    time.sleep(5)
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}}
    for tentativa in range(3):
        r = requests.post(GEMINI_URL, json=payload, timeout=90)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        elif r.status_code == 429:
            print(f"  Rate limit aguardando 60s ({tentativa+1}/3)")
            time.sleep(60)
        else:
            print(f"  Gemini {r.status_code}: {r.text[:200]}")
            return None
    return None

def get_or_create_category(slug, name):
    r = requests.get(f"{WP_API}/categories", headers=WP_HEADERS, params={"slug": slug})
    cats = r.json()
    if isinstance(cats, list) and cats:
        return cats[0]["id"]
    nova = requests.post(f"{WP_API}/categories", headers=WP_HEADERS, json={"name": name, "slug": slug})
    return nova.json().get("id")

def get_tag(ticker):
    r = requests.get(f"{WP_API}/tags", headers=WP_HEADERS, params={"search": ticker})
    tags = r.json()
    if isinstance(tags, list) and tags:
        return tags[0]["id"]
    nova = requests.post(f"{WP_API}/tags", headers=WP_HEADERS, json={"name": ticker})
    return nova.json().get("id")

def publicar(titulo, conteudo, categoria, ticker):
    tag_id = get_tag(ticker)
    r = requests.post(f"{WP_API}/posts", headers=WP_HEADERS, json={
        "title": titulo, "content": conteudo,
        "status": "publish", "categories": [categoria],
        "tags": [tag_id] if tag_id else []
    })
    if r.status_code in (200, 201):
        url = r.json()["link"]
        print(f"  OK {url}")
        return url
    print(f"  WP ERRO {r.status_code}: {r.text[:300]}")
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

def proximos(lista, controle, semana, n):
    pendentes = []
    for ativo in lista:
        t = ativo["ticker"]
        chave = f"{t}_{semana}"
        if chave not in controle or controle[chave].get("status") != "ok":
            ultima = controle.get(f"{t}_ultima", "0")
            pendentes.append((ultima, ativo))
    pendentes.sort(key=lambda x: x[0])
    return [a for _, a in pendentes[:n]]

def processar_ativo(ativo, controle, semana, cat, tipo):
    t = ativo["ticker"]
    chave = f"{t}_{semana}"
    print(f"  -> {t} ({ativo['nome']})")
    if tipo == "fii":
        prompt = PROMPT_FII.format(
            ticker=t, nome=ativo["nome"], ri_url=ativo.get("ri_url",""),
            tipo=ativo.get("tipo",""), gestora=ativo.get("gestora",""))
    else:
        prompt = PROMPT_ACAO.format(
            ticker=t, nome=ativo["nome"], ri_url=ativo.get("ri_url",""),
            setor=ativo.get("setor",""))
    print("     Gemini...")
    analise = gemini(prompt)
    if not analise:
        controle[chave] = {"status": "erro_gemini"}
        salvar(CONTROLE, controle)
        return
    mes = datetime.today().strftime("%m/%Y")
    titulo = f"{t} - {ativo['nome']} | Analise {mes}"
    print("     Publicando...")
    url = publicar(titulo, analise, cat, t)
    if url:
        atualizar_ranking(t, url, tipo)
        controle[chave] = {"status": "ok", "url": url, "data": datetime.today().strftime("%Y-%m-%d")}
        controle[f"{t}_ultima"] = datetime.today().strftime("%Y-%m-%d")
    else:
        controle[chave] = {"status": "erro_wp"}
    salvar(CONTROLE, controle)

def main():
    print(f"Manjubinha - {datetime.today().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Rodada: 2 FIIs + 2 Acoes")
    config   = carregar("config.json", {})
    controle = carregar(CONTROLE, {})
    semana   = semana_atual()
    print(f"Semana: {semana}")
    cat_fiis  = get_or_create_category("analises-fiis", "FIIs | Analises")
    cat_acoes = get_or_create_category("documentos-acoes", "Acoes | Analises")
    fiis_rodada  = proximos(config.get("fiis",  []), controle, semana, POR_RODADA)
    acoes_rodada = proximos(config.get("acoes", []), controle, semana, POR_RODADA)
    if not fiis_rodada and not acoes_rodada:
        print("Todos os 60 ativos ja analisados esta semana!")
        return
    print(f"FIIs: {[a['ticker'] for a in fiis_rodada]}")
    for ativo in fiis_rodada:
        processar_ativo(ativo, controle, semana, cat_fiis, "fii")
    print(f"Acoes: {[a['ticker'] for a in acoes_rodada]}")
    for ativo in acoes_rodada:
        processar_ativo(ativo, controle, semana, cat_acoes, "acao")
    pf = len(proximos(config.get("fiis",[]),  controle, semana, 99))
    pa = len(proximos(config.get("acoes",[]), controle, semana, 99))
    print(f"Concluido! Restam {pf} FIIs e {pa} Acoes esta semana.")

if __name__ == "__main__":
    main()
