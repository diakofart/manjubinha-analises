"""
Manjubinha Investidor — Script de Análises Automáticas
Roda 2x por semana (terça e sexta) via GitHub Actions.
Busca documentos novos nos sites de RI dos 60 ativos,
analisa com Gemini API (gratuito) e publica no WordPress.com.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ── Configurações ──────────────────────────────────────────────────────────────
WP_SITE      = "manjubinhainvestidor.wordpress.com"
WP_TOKEN    = os.environ["WP_TOKEN"]

GEMINI_KEY   = os.environ["GEMINI_API_KEY"]

WP_API       = f"https://public-api.wordpress.com/wp/v2/sites/{WP_SITE}"
WP_AUTH     = None  # usando token Bearer
GEMINI_URL   = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"

CAT_FIIS     = 790154326
CAT_ACOES    = 790154327
CONTROLE     = Path("controle_docs.json")

# ── Prompts ────────────────────────────────────────────────────────────────────

PROMPT_FII = """
Você é um analista financeiro do site Manjubinha Investidor, que cria análises
simplificadas de FIIs para investidores iniciantes e intermediários.

Com base no documento do FII {ticker} ({nome}) abaixo, escreva uma análise
completa em HTML puro (sem markdown, sem ```) seguindo EXATAMENTE esta estrutura:

<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group">
  <!-- wp:heading {{"level":4}} -->
  <h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO — PERÍODO</mark></h4>
  <!-- /wp:heading -->
  <!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} -->
  <p style="font-size:14px">Publicado em: DD/MM/AAAA — <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial do fundo ({gestora}) ↗</a></p>
  <!-- /wp:paragraph -->
  <!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} -->
  <p style="font-size:14px">Tipo: {tipo} — Gestora: {gestora}</p>
  <!-- /wp:paragraph -->
</div>
<!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">💬 O que esse fundo faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Indicador: valor</strong> — explicação curta em uma linha.</p><!-- /wp:paragraph -->
(repita para cada indicador relevante)

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🎯 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Analise se o DY está inflado por extraordinários. Se for fundo de papel, SEMPRE inclua: "⚠️ <strong>Atenção para fundos de papel:</strong> Fundos como o {ticker} não devem ser comprados com P/VP acima de 1,0. Diferente dos fundos de tijolo, não há imóveis que se valorizam — pagar acima do valor da carteira de CRIs raramente se justifica."</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI — resposta direta (Sim/Não) com explicação curta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: ✅/⚠️/❌ RESULTADO</strong><br>Explicação curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização: ✅/⚠️/❌ RESULTADO</strong><br>Explicação curta.</p><!-- /wp:paragraph -->

<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>📌 Conclusão final em 2-3 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras:
- Substitua os ESCREVA AQUI com conteúdo real baseado no documento
- Linguagem simples, sem jargões, máximo 600 palavras
- Seja específico com números do documento
- NÃO inclua markdown, apenas o HTML acima

DOCUMENTO:
{conteudo_doc}
"""

PROMPT_ACAO = """
Você é um analista financeiro do site Manjubinha Investidor, que cria análises
simplificadas de Ações para investidores iniciantes e intermediários.

Com base no documento da empresa {ticker} ({nome}) abaixo, escreva uma análise
completa em HTML puro (sem markdown, sem ```) seguindo EXATAMENTE esta estrutura:

<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group">
  <!-- wp:heading {{"level":4}} -->
  <h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO — PERÍODO</mark></h4>
  <!-- /wp:heading -->
  <!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} -->
  <p style="font-size:14px">Publicado em: DD/MM/AAAA — <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial de RI ({nome}) ↗</a></p>
  <!-- /wp:paragraph -->
  <!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} -->
  <p style="font-size:14px">Setor: {setor} — Empresa: {nome}</p>
  <!-- /wp:paragraph -->
</div>
<!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">💬 O que essa empresa faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Indicador: valor</strong> — explicação curta em uma linha.</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🎯 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Analise se o DY está dentro do padrão histórico ou inflado por extraordinários. Seja direto.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI — resposta direta (Sim/Não) com explicação curta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: ✅/⚠️/❌ RESULTADO</strong><br>Explicação curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização: ✅/⚠️/❌ RESULTADO</strong><br>Explicação curta.</p><!-- /wp:paragraph -->

<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>📌 Conclusão final em 2-3 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras:
- Substitua os ESCREVA AQUI com conteúdo real baseado no documento
- Linguagem simples, sem jargões, máximo 600 palavras
- Seja específico com números do documento
- NÃO inclua markdown, apenas o HTML acima

DOCUMENTO:
{conteudo_doc}
"""

# ── Funções auxiliares ─────────────────────────────────────────────────────────

def carregar_controle():
    if CONTROLE.exists():
        return json.loads(CONTROLE.read_text())
    return {}

def salvar_controle(controle):
    CONTROLE.write_text(json.dumps(controle, indent=2, ensure_ascii=False))

def carregar_config():
    return json.loads(Path("config.json").read_text())

def carregar_ranking():
    return json.loads(Path("ranking.json").read_text())

def salvar_ranking(ranking):
    Path("ranking.json").write_text(json.dumps(ranking, indent=2, ensure_ascii=False))

def analisar_com_gemini(prompt):
    """Envia prompt para Gemini Flash e retorna o texto gerado."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        }
    }
    resp = requests.post(GEMINI_URL, json=payload, timeout=60)
    if resp.status_code == 200:
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    else:
        print(f"  ❌ Erro Gemini: {resp.status_code} — {resp.text[:300]}")
        return None

def buscar_pdf_fii(ativo, desde_data):
    """Busca documentos novos no FundosNet para FIIs."""
    docs = []
    tipos_relevantes = ["Relatório Mensal", "Fato Relevante", "Informe Mensal", "Comunicado ao Mercado"]
    try:
        params = {
            "tipoFundo": "FII",
            "cnpj": ativo.get("fundosnet_cnpj", ""),
            "dataInicial": desde_data.strftime("%Y-%m-%d"),
            "dataFinal": datetime.today().strftime("%Y-%m-%d"),
        }
        resp = requests.get(
            "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarDocumentos",
            params=params, timeout=15
        )
        if resp.status_code == 200:
            for doc in resp.json().get("data", {}).get("list", []):
                tipo = doc.get("tipoDocumento", {}).get("descricao", "")
                if any(t in tipo for t in tipos_relevantes):
                    docs.append({
                        "titulo": f"{tipo} — {doc.get('competencia', '')}",
                        "url": f"https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={doc.get('id')}",
                        "data": doc.get("dataEntrega", "")[:10],
                        "tipo": tipo
                    })
    except Exception as e:
        print(f"  ⚠️  Erro FundosNet {ativo['ticker']}: {e}")
    return docs

def buscar_doc_acao(ativo, desde_data):
    """Busca documentos novos no ENET/CVM para Ações."""
    docs = []
    try:
        params = {
            "q": ativo["ticker"],
            "dateRange": "custom",
            "startDate": desde_data.strftime("%Y-%m-%d"),
            "endDate": datetime.today().strftime("%Y-%m-%d"),
            "category": "ITR,DFP,PRESS",
        }
        resp = requests.get(
            "https://efts.cvm.gov.br/EFTS/unif/busca",
            params=params, timeout=15
        )
        if resp.status_code == 200:
            for hit in resp.json().get("hits", {}).get("hits", []):
                src = hit.get("_source", {})
                categoria = src.get("categoria", "")
                if any(c in categoria for c in ["Trimestral", "Release", "Resultado", "ITR"]):
                    docs.append({
                        "titulo": src.get("titulo", categoria),
                        "url": src.get("linkDownload", ativo["ri_url"]),
                        "data": src.get("dataReferencia", "")[:10],
                        "tipo": categoria
                    })
    except Exception as e:
        print(f"  ⚠️  Erro CVM {ativo['ticker']}: {e}")
    return docs

def baixar_texto_pdf(url_pdf):
    """Baixa PDF e extrai texto das primeiras 15 páginas."""
    try:
        resp = requests.get(url_pdf, timeout=30)
        if resp.status_code == 200:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(resp.content))
            texto = "\n".join(page.extract_text() or "" for page in reader.pages[:15])
            return texto[:12000]
    except Exception as e:
        print(f"  ⚠️  Erro PDF: {e}")
    return None

def publicar_post_wp(titulo, conteudo, ativo, tipo="fii"):
    """Publica post no WordPress.com e retorna a URL."""
    categoria = CAT_FIIS if tipo == "fii" else CAT_ACOES

    # Busca ou cria tag para o ticker
    tag_id = None
    try:
        r = requests.get(f"{WP_API}/tags", params={"search": ativo["ticker"]}, headers={"Authorization": f"Bearer {WP_TOKEN}"})
        tags = r.json()
        if tags:
            tag_id = tags[0]["id"]
        else:
            nova = requests.post(f"{WP_API}/tags", json={"name": ativo["ticker"]}, headers={"Authorization": f"Bearer {WP_TOKEN}"}).json()
            tag_id = nova.get("id")
    except Exception as e:
        print(f"  ⚠️  Erro tag: {e}")

    post_data = {
        "title": titulo,
        "content": conteudo,
        "status": "publish",
        "categories": [categoria],
        "tags": [tag_id] if tag_id else [],
    }

    resp = requests.post(f"{WP_API}/posts", json=post_data, headers={"Authorization": f"Bearer {WP_TOKEN}"})
    if resp.status_code in (200, 201):
        url = resp.json()["link"]
        print(f"  ✅ Publicado: {url}")
        return url
    else:
        print(f"  ❌ Erro WP: {resp.status_code} — {resp.text[:200]}")
        return None

def atualizar_ranking(ticker, post_url, tipo="fii"):
    """Adiciona link do novo post no ranking.json."""
    ranking = carregar_ranking()
    lista = ranking["fiis"] if tipo == "fii" else ranking["acoes"]
    for item in lista:
        if item["ticker"] == ticker:
            item["post_url"] = post_url
            break
    ranking["ultima_atualizacao"] = datetime.today().strftime("%Y-%m-%d")
    salvar_ranking(ranking)

# ── Fluxo principal ────────────────────────────────────────────────────────────

def processar(config_lista, controle, desde_data, tipo):
    label = "FIIs" if tipo == "fii" else "Ações"
    print(f"\n{'📦' if tipo == 'fii' else '📈'} Processando {label}...")

    for ativo in config_lista:
        ticker = ativo["ticker"]
        print(f"\n  → {ticker} ({ativo['nome']})")

        docs = buscar_pdf_fii(ativo, desde_data) if tipo == "fii" else buscar_doc_acao(ativo, desde_data)

        if not docs:
            print(f"     Nenhum documento novo.")
            continue

        for doc in docs:
            doc_id = f"{ticker}_{doc['data']}_{doc.get('tipo','')[:20]}"
            if doc_id in controle:
                print(f"     Já processado: {doc['titulo']}")
                continue

            print(f"     📄 Novo: {doc['titulo']}")
            texto = baixar_texto_pdf(doc["url"])
            if not texto:
                print(f"     ⚠️  Não foi possível extrair texto.")
                controle[doc_id] = {"status": "erro_pdf", "data": doc["data"]}
                salvar_controle(controle)
                continue

            print(f"     🤖 Analisando com Gemini...")
            template = PROMPT_FII if tipo == "fii" else PROMPT_ACAO

            if tipo == "fii":
                prompt = template.format(
                    ticker=ativo["ticker"],
                    nome=ativo["nome"],
                    ri_url=ativo["ri_url"],
                    tipo=ativo.get("tipo", ""),
                    gestora=ativo.get("gestora", ""),
                    conteudo_doc=texto
                )
            else:
                prompt = template.format(
                    ticker=ativo["ticker"],
                    nome=ativo["nome"],
                    ri_url=ativo["ri_url"],
                    setor=ativo.get("setor", ""),
                    conteudo_doc=texto
                )

            analise = analisar_com_gemini(prompt)
            if not analise:
                controle[doc_id] = {"status": "erro_gemini", "data": doc["data"]}
                salvar_controle(controle)
                continue

            titulo_post = f"{ticker} — {ativo['nome']} | {doc['titulo']}"
            print(f"     📝 Publicando...")
            url = publicar_post_wp(titulo_post, analise, ativo, tipo=tipo)

            if url:
                atualizar_ranking(ticker, url, tipo=tipo)
                controle[doc_id] = {"status": "ok", "data": doc["data"], "url": url}
            else:
                controle[doc_id] = {"status": "erro_wp", "data": doc["data"]}

            salvar_controle(controle)

def main():
    print("🐟 Manjubinha Analises — Iniciando")
    print(f"   {datetime.today().strftime('%Y-%m-%d %H:%M UTC')}")

    config   = carregar_config()
    controle = carregar_controle()

    # Primeira execução: retroativo de junho/2026
    # Execuções seguintes: últimos 8 dias
    if not controle:
        print("   📅 Primeira execução — retroativo desde 01/06/2026")
        desde_data = datetime(2026, 6, 1)
    else:
        print("   📅 Buscando documentos dos últimos 8 dias")
        desde_data = datetime.today() - timedelta(days=8)

    processar(config["fiis"],  controle, desde_data, tipo="fii")
    processar(config["acoes"], controle, desde_data, tipo="acao")

    print("\n✅ Concluído!")

if __name__ == "__main__":
    main()
