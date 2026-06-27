"""
Manjubinha Investidor - Analises Automaticas
Roda 4x por dia (a cada 6h). Processa 2 FIIs + 2 Acoes por rodada.
Carrossel continuo: publica o doc mais recente de cada ativo via Investidor10.
Controle por ID do documento - nunca repete o mesmo doc.
"""

import os, json, requests, time, re
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

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

INV10_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Manjubinha/1.0)"}

PROMPT_FII = """Voce e analista do site Manjubinha Investidor. Pesquise informacoes recentes do FII {ticker} ({nome}) com base no documento: {descricao_doc} de {data_doc} (link: {url_doc}).
Escreva uma analise completa em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group"><!-- wp:heading {"level":4} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">{descricao_doc} - {data_doc}</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Publicado em: {data_doc} - <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial do fundo ({gestora})</a></p><!-- /wp:paragraph -->
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

PROMPT_ACAO = """Voce e analista do site Manjubinha Investidor. Pesquise informacoes recentes da empresa {ticker} ({nome}) com base no documento: {descricao_doc} de {data_doc} (link: {url_doc}).
Escreva uma analise completa em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group"><!-- wp:heading {"level":4} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">{descricao_doc} - {data_doc}</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {"style":{"typography":{"fontSize":"14px"}}} --><p style="font-size:14px">Publicado em: {data_doc} - <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial de RI ({nome})</a></p><!-- /wp:paragraph -->
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

def buscar_ultimo_doc(ticker, inv10_tipo):
    """
    Raspa o Investidor10 e retorna o documento mais recente do ativo.
    inv10_tipo: "fiis" ou "acoes"
    Retorna: {"id": str, "descricao": str, "data": str, "url_doc": str} ou None
    """
    url = f"https://investidor10.com.br/{inv10_tipo}/{ticker.lower()}/"
    try:
        r = requests.get(url, timeout=15, headers=INV10_HEADERS)
        if r.status_code != 200:
            print(f"  Investidor10 {r.status_code} para {ticker}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        link = soup.find("a", href=re.compile(r"link_comunicado"))
        if not link:
            print(f"  Nenhum comunicado encontrado para {ticker}")
            return None
        href = link["href"]
        doc_id = href.rstrip("/").split("/")[-1]
        # Extrai descricao e data via classes do Investidor10 (communication-card)
        # usa match exato para evitar bater em communication-card--disclosure
        card = link.find_parent("div", class_="communication-card")
        descricao, data = "Comunicado", ""
        if card:
            p = card.find("p", class_="communication-card--content")
            span = card.find("span", class_="card-date--content")
            if p:
                descricao = p.get_text(strip=True)[:100]
            if span:
                data = span.get_text(strip=True)
        return {"id": doc_id, "descricao": descricao, "data": data, "url_doc": href}
    except Exception as e:
        print(f"  Erro scraping {ticker}: {e}")
        return None

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
    """
    Retorna:
      str   -> analise gerada com sucesso (ja sem markdown)
      None  -> falha por quota (429): nao gravar, retentar na proxima rodada
      False -> erro permanente: marcar sem_analise
    """
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
        elif r.status_code == 503:
            print(f"  503 sobrecarga: aguardando 30s ({tentativa+1}/3)")
            time.sleep(30)
        else:
            so_quota = False
            print(f"  Gemini {r.status_code}: {r.text[:200]}")
            return False
    if so_quota:
        print("  Gemini indisponivel apos 3 tentativas - retentara na proxima rodada")
        return None
    return False

# Categorias fixas do WordPress Manjubinha Hostinger
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
    """Retorna os N ativos com a data de ultima analise mais antiga (carrossel continuo)."""
    pendentes = []
    for ativo in lista:
        t = ativo["ticker"]
        ultima = controle.get(t, {}).get("ultima", "0")
        pendentes.append((ultima, ativo))
    pendentes.sort(key=lambda x: x[0])
    return [a for _, a in pendentes[:n]]

def processar_ativo(ativo, controle, tipo):
    t    = ativo["ticker"]
    hoje = datetime.today().strftime("%Y-%m-%d")
    print(f"  -> {t} ({ativo['nome']})")

    # 1. Busca ultimo doc no Investidor10
    inv10_tipo = "fiis" if tipo == "fii" else "acoes"
    doc = buscar_ultimo_doc(t, inv10_tipo)
    if not doc:
        print(f"  {t} sem doc disponivel - tentara na proxima rodada")
        return  # nao atualiza ultima: ativo fica no inicio da fila para retentar logo

    # 2. Verifica se esse doc ja foi publicado
    chave = f"{t}_{doc['id']}"
    if controle.get(chave, {}).get("status") == "ok":
        print(f"  {t} doc ja publicado ({doc['descricao']} | {doc['data']}) - sem novidade")
        controle.setdefault(t, {})["ultima"] = hoje  # empurra para o fim da fila
        salvar(CONTROLE, controle)
        return

    # 3. Monta prompt com info do documento
    print(f"  Novo doc: {doc['descricao']} ({doc['data']})")
    if tipo == "fii":
        prompt = PROMPT_FII \
            .replace("{ticker}", t) \
            .replace("{nome}", ativo["nome"]) \
            .replace("{descricao_doc}", doc["descricao"]) \
            .replace("{data_doc}", doc["data"]) \
            .replace("{url_doc}", doc["url_doc"]) \
            .replace("{ri_url}", ativo.get("ri_url", "")) \
            .replace("{tipo}", ativo.get("tipo", "")) \
            .replace("{gestora}", ativo.get("gestora", ""))
        categorias = get_fii_categories(ativo)
    else:
        prompt = PROMPT_ACAO \
            .replace("{ticker}", t) \
            .replace("{nome}", ativo["nome"]) \
            .replace("{descricao_doc}", doc["descricao"]) \
            .replace("{data_doc}", doc["data"]) \
            .replace("{url_doc}", doc["url_doc"]) \
            .replace("{ri_url}", ativo.get("ri_url", "")) \
            .replace("{setor}", ativo.get("setor", ""))
        categorias = get_acao_categories(ativo)

    print(f"  Categorias: {categorias}")
    print("  Gemini...")
    analise = gemini(prompt)

    if analise is None:
        print(f"  {t} adiado - quota Gemini, retenta na proxima rodada")
        return  # nao atualiza ultima nem chave

    if analise is False:
        print(f"  {t} erro permanente Gemini - marcando doc como sem_analise")
        controle[chave] = {"status": "sem_analise", "data": hoje}
        controle.setdefault(t, {})["ultima"] = hoje
        salvar(CONTROLE, controle)
        return

    mes    = datetime.today().strftime("%m/%Y")
    titulo = f"{t} - {ativo['nome']} | {doc['descricao']} {mes}"
    print("  Publicando...")
    url = publicar(titulo, analise, categorias, t)
    if url:
        atualizar_ranking(t, url, tipo)
        controle[chave] = {"status": "ok", "url": url, "data": hoje, "descricao": doc["descricao"]}
        controle.setdefault(t, {})["ultima"] = hoje
        salvar(CONTROLE, controle)
        print(f"  Salvo: {chave}")
    else:
        print(f"  {t} erro WP - retenta na proxima rodada")
        # nao atualiza: retenta logo

def main():
    print(f"Manjubinha - {datetime.today().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Rodada: 2 FIIs + 2 Acoes")
    config   = carregar("config.json", {})
    controle = carregar(CONTROLE, {})
    fiis_rodada  = proximos(config.get("fiis",  []), controle, POR_RODADA)
    acoes_rodada = proximos(config.get("acoes", []), controle, POR_RODADA)
    if not fiis_rodada and not acoes_rodada:
        print("Nenhum ativo configurado.")
        return
    print(f"FIIs:  {[a['ticker'] for a in fiis_rodada]}")
    for ativo in fiis_rodada:
        processar_ativo(ativo, controle, "fii")
    print(f"Acoes: {[a['ticker'] for a in acoes_rodada]}")
    for ativo in acoes_rodada:
        processar_ativo(ativo, controle, "acao")
    # Resumo
    total_fiis  = len(config.get("fiis",  []))
    total_acoes = len(config.get("acoes", []))
    hoje = datetime.today().strftime("%Y-%m-%d")
    atualizados_f = sum(1 for a in config.get("fiis",  []) if controle.get(a["ticker"], {}).get("ultima") == hoje)
    atualizados_a = sum(1 for a in config.get("acoes", []) if controle.get(a["ticker"], {}).get("ultima") == hoje)
    print(f"Concluido! Verificados hoje: {atualizados_f}/{total_fiis} FIIs, {atualizados_a}/{total_acoes} Acoes.")

if __name__ == "__main__":
    main()
