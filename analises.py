"""
Manjubinha Investidor - Analises Automaticas
Roda 4x por dia (a cada 6h). Processa 2 FIIs + 2 Acoes por rodada.
Ciclo carrossel: cobre todos os ~60 ativos antes de repetir qualquer um.
"""

import os, json, requests, time
from datetime import datetime
from pathlib import Path

# Config
WP_URL    = "https://manjubinhainvestidor.com.br"
WP_USER   = os.environ["WP_USER"]
WP_PASS   = os.environ["WP_APP_PASS"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

WP_API = f"{WP_URL}/wp-json/wp/v2"
import base64
_cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
WP_HEADERS = {"Authorization": f"Basic {_cred}"}

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"

CONTROLE   = Path("controle_docs.json")
POR_RODADA = 2  # 2 FIIs + 2 Acoes = 4 por rodada

# Status que contam como "concluido" no ciclo (nao retentam nem bloqueiam avanco)
STATUS_CONCLUIDO = ("ok", "sem_analise")

PROMPT_FII = """Voce e analista do site Manjubinha Investidor. Pesquise informacoes recentes do FII {ticker} ({nome}) e escreva uma analise completa em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group"><!-- wp:heading {"level":4} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO - PERIODO</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Publicado em: DD/MM/AAAA - <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial do fundo ({gestora})</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Tipo: {tipo} - Gestora: {gestora}</p><!-- /wp:paragraph --></div><!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">💬 O que esse fundo faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>DY mensal: X%</strong> - explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>P/VP: X,XX</strong> - explicacao curta.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">💰 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Analise se o DY esta dentro do padrao. Se fundo de papel: Fundos de papel nao devem ser comprados com P/VP acima de 1,0.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">⚠️ Pontos de Atencao</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">✅ Boa Noticia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Sim ou Nao com explicacao direta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: RESULTADO</strong><br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorizacao: RESULTADO</strong><br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>Conclusao em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras: linguagem simples, maximo 600 palavras, numeros reais, sem markdown extra."""

PROMPT_ACAO = """Voce e analista do site Manjubinha Investidor. Pesquise informacoes recentes da empresa {ticker} ({nome}) e escreva uma analise completa em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group"><!-- wp:heading {"level":4} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO - PERIODO</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Publicado em: DD/MM/AAAA - <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial de RI ({nome})</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Setor: {setor} - Empresa: {nome}</p><!-- /wp:paragraph --></div><!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">💬 O que essa empresa faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Receita: R$ X bi</strong> - explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Lucro: R$ X bi</strong> - explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>DY anual: X%</strong> - explicacao curta.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">💰 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>DY dentro do padrao historico ou inflado por extraordinarios?</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">⚠️ Pontos de Atencao</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">✅ Boa Noticia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Sim ou Nao com explicacao direta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: RESULTADO</strong><br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorizacao: RESULTADO</strong><br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>Conclusao em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras: linguagem simples, maximo 600 palavras, numeros reais, sem markdown extra."""

def carregar(path, default):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default

def salvar(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

def limpar_markdown(texto):
    """Remove blocos de codigo markdown que modelos mais novos adicionam mesmo sem pedir."""
    texto = texto.strip()
    fence = chr(96) * 3
    if texto.startswith(fence):
        linhas = texto.split("\n")
        linhas = linhas[1:]
        if linhas and linhas[-1].strip() == fence:
            linhas = linhas[:-1]
        texto = "\n".join(linhas).strip()
    return texto

def gemini(prompt):
    time.sleep(5)
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}}
    so_quota = True
    for tentativa in range(3):
        r = requests.post(GEMINI_URL, json=payload, timeout=90)
        if r.status_code == 200:
            texto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return limpar_markdown(texto)
        elif r.status_code == 429:
            print(f"  429 quota: aguardando 60s ({tentativa+1}/3)")
            time.sleep(60)
        else:
            so_quota = False
            print(f"  Gemini {r.status_code}: {r.text[:200]}")
            return False
    if so_quota:
        print("  Quota esgotada apos 3 tentativas - retentara na proxima rodada")
        return None
    return False

CAT_FII_PRINCIPAL = 13
CAT_ACAO_PRINCIPAL = 2

CAT_FII_TIPO = {
    "Papel": 30, "papel": 30,
    "Tijolo": 31, "tijolo": 31,
    "FoF": 26, "fof": 26,
    "Hibrido": 27, "hibrido": 27,
    "Fiagro": 25, "fiagro": 25,
}

CAT_FII_SEG = {
    "Logistico": 19,
    "Shoppings": 22,
    "Lajes Corp.": 18,
    "TVM": 23,
}

CAT_ACAO_SETOR = {
    "Bens Industriais": 3,
    "Consumo Ciclico": 4,
    "Consumo Nao Ciclico": 5,
    "Financeiro": 6,
    "Materiais Basicos": 7,
    "Petroleo, Gas e Biocombustiveis": 8,
    "Saude": 9,
    "Tecnologia da Informacao": 10,
    "Telecomunicacoes": 11,
    "Utilidade Publica": 12,
}

def get_fii_categories(ativo):
    cats = [CAT_FII_PRINCIPAL]
    tipo = ativo.get("tipo", "")
    seg  = ativo.get("segmento", "")
    if tipo.lower() == "tijolo" and seg:
        cat = CAT_FII_SEG.get(seg)
        cats.append(cat if cat else 31)
    elif tipo:
        cat = CAT_FII_TIPO.get(tipo)
        if cat:
            cats.append(cat)
    return cats

def get_acao_categories(ativo):
    cats = [CAT_ACAO_PRINCIPAL]
    setor = ativo.get("setor", "")
    cat = CAT_ACAO_SETOR.get(setor)
    if cat:
        cats.append(cat)
    return cats

def get_tag(ticker):
    r = requests.get(f"{WP_API}/tags", headers=WP_HEADERS, params={"search": ticker})
    tags = r.json()
    if isinstance(tags, list) and tags:
        return tags[0]["id"]
    nova = requests.post(f"{WP_API}/tags", headers=WP_HEADERS, json={"name": ticker})
    return nova.json().get("id")

def publicar(titulo, conteudo, categorias, ticker):
    tag_id = get_tag(ticker)
    r = requests.post(f"{WP_API}/posts", headers=WP_HEADERS, json={
        "title": titulo, "content": conteudo,
        "status": "publish", "categories": categorias,
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

def proximos(lista, controle, n):
    ciclo = controle.get("ciclo_atual", 1)
    pendentes = []
    for ativo in lista:
        t = ativo["ticker"]
        entrada = controle.get(t, {})
        if entrada.get("status") in STATUS_CONCLUIDO and entrada.get("ciclo") == ciclo:
            continue
        ultima = entrada.get("ultima", "0")
        pendentes.append((ultima, ativo))
    pendentes.sort(key=lambda x: x[0])
    return [a for _, a in pendentes[:n]]

def processar_ativo(ativo, controle, tipo):
    t     = ativo["ticker"]
    ciclo = controle.get("ciclo_atual", 1)
    hoje  = datetime.today().strftime("%Y-%m-%d")
    print(f"  -> {t} ({ativo['nome']})")
    if tipo == "fii":
        prompt = PROMPT_FII.replace("{ticker}", t).replace("{nome}", ativo["nome"]).replace("{ri_url}", ativo.get("ri_url", "")).replace("{tipo}", ativo.get("tipo", "")).replace("{gestora}", ativo.get("gestora", ""))
        categorias = get_fii_categories(ativo)
    else:
        prompt = PROMPT_ACAO.replace("{ticker}", t).replace("{nome}", ativo["nome"]).replace("{ri_url}", ativo.get("ri_url", "")).replace("{setor}", ativo.get("setor", ""))
        categorias = get_acao_categories(ativo)
    print(f"  Categorias: {categorias}")
    print("  Gemini...")
    analise = gemini(prompt)
    if analise is None:
        print(f"  {t} adiado - quota Gemini, retenta na proxima rodada")
        return
    if analise is False:
        print(f"  {t} marcado como sem_analise - nao bloqueara o proximo ciclo")
        controle[t] = {"status": "sem_analise", "ciclo": ciclo, "data": hoje, "ultima": controle.get(t, {}).get("ultima", "0")}
        salvar(CONTROLE, controle)
        return
    mes    = datetime.today().strftime("%m/%Y")
    titulo = f"{t} - {ativo['nome']} | Analise {mes}"
    print("  Publicando...")
    url = publicar(titulo, analise, categorias, t)
    if url:
        atualizar_ranking(t, url, tipo)
        controle[t] = {"status": "ok", "url": url, "data": hoje, "ciclo": ciclo, "ultima": controle.get(t, {}).get("ultima", "0")}
        salvar(CONTROLE, controle)
        print(f"  Salvo (ciclo {ciclo})")
    else:
        print(f"  {t} adiado - erro WP, retenta na proxima rodada")

def verificar_e_avancar_ciclo(config, controle):
    ciclo = controle.get("ciclo_atual", 1)
    todos = config.get("fiis", []) + config.get("acoes", [])
    feitos = sum(1 for a in todos if controle.get(a["ticker"], {}).get("status") in STATUS_CONCLUIDO and controle.get(a["ticker"], {}).get("ciclo") == ciclo)
    total = len(todos)
    print(f"Progresso ciclo {ciclo}: {feitos}/{total} ativos concluidos")
    if total > 0 and feitos == total:
        hoje = datetime.today().strftime("%Y-%m-%d")
        for a in todos:
            t = a["ticker"]
            if t in controle:
                controle[t]["ultima"] = controle[t].get("data", hoje)
        controle["ciclo_atual"] = ciclo + 1
        salvar(CONTROLE, controle)
        print(f"Ciclo {ciclo} completo! Iniciando ciclo {ciclo + 1}")

def main():
    print(f"Manjubinha - {datetime.today().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Rodada: 2 FIIs + 2 Acoes")
    config   = carregar("config.json", {})
    controle = carregar(CONTROLE, {"ciclo_atual": 1})
    ciclo    = controle.get("ciclo_atual", 1)
    print(f"Ciclo atual: {ciclo}")
    fiis_rodada  = proximos(config.get("fiis",  []), controle, POR_RODADA)
    acoes_rodada = proximos(config.get("acoes", []), controle, POR_RODADA)
    if not fiis_rodada and not acoes_rodada:
        print("Todos os ativos ja analisados neste ciclo!")
        verificar_e_avancar_ciclo(config, controle)
        return
    print(f"FIIs:  {[a['ticker'] for a in fiis_rodada]}")
    for ativo in fiis_rodada:
        processar_ativo(ativo, controle, "fii")
    print(f"Acoes: {[a['ticker'] for a in acoes_rodada]}")
    for ativo in acoes_rodada:
        processar_ativo(ativo, controle, "acao")
    verificar_e_avancar_ciclo(config, controle)
    pf = len(proximos(config.get("fiis",  []), controle, 99))
    pa = len(proximos(config.get("acoes", []), controle, 99))
    print(f"Concluido! Restam {pf} FIIs e {pa} Acoes neste ciclo.")

if __name__ == "__main__":
    main()
