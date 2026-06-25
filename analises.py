"""
Manjubinha Investidor — Script de Análises Automáticas
Roda 2x por semana via GitHub Actions.
"""

import os, json, requests
from datetime import datetime, timedelta
from pathlib import Path
from busca import buscar_docs_fii, buscar_docs_acao

# ── Config ─────────────────────────────────────────────────────────────────────
WP_SITE    = "manjubinhainvestidor.wordpress.com"
WP_TOKEN   = os.environ["WP_TOKEN"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

WP_API     = f"https://public-api.wordpress.com/wp/v2/sites/{WP_SITE}"
WP_HEADERS = {"Authorization": f"Bearer {WP_TOKEN}"}
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"

CAT_FIIS   = 790154326
CAT_ACOES  = 790154327
CONTROLE   = Path("controle_docs.json")

# ── Prompts ────────────────────────────────────────────────────────────────────
PROMPT_FII = """Você é analista do site Manjubinha Investidor. Com base no documento do FII {ticker} ({nome}) abaixo, escreva uma análise em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:heading {{"level":4}} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO — PERÍODO</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Publicado em: DD/MM/AAAA — <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial do fundo ({gestora}) ↗</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Tipo: {tipo} — Gestora: {gestora}</p><!-- /wp:paragraph --></div><!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">💬 O que esse fundo faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Indicador: valor</strong> — explicação curta.</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🎯 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI. Se fundo de papel: inclua "⚠️ <strong>Atenção:</strong> Fundos de papel não devem ser comprados com P/VP acima de 1,0 — você estaria pagando mais do que a carteira de CRIs vale, sem imóveis para compensar."</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI — Sim ou Não com explicação direta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: ✅/⚠️/❌</strong><br>Explicação.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização: ✅/⚠️/❌</strong><br>Explicação.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>📌 Conclusão em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras: linguagem simples, máximo 600 palavras, números reais do documento, sem markdown.

DOCUMENTO:
{conteudo_doc}"""

PROMPT_ACAO = """Você é analista do site Manjubinha Investidor. Com base no documento da empresa {ticker} ({nome}) abaixo, escreva uma análise em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:heading {{"level":4}} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO — PERÍODO</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Publicado em: DD/MM/AAAA — <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial de RI ({nome}) ↗</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Setor: {setor} — Empresa: {nome}</p><!-- /wp:paragraph --></div><!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">💬 O que essa empresa faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Indicador: valor</strong> — explicação curta.</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🎯 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI — DY dentro do padrão ou inflado por extraordinários?</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA AQUI — Sim ou Não com explicação direta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: ✅/⚠️/❌</strong><br>Explicação.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização: ✅/⚠️/❌</strong><br>Explicação.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>📌 Conclusão em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

Regras: linguagem simples, máximo 600 palavras, números reais do documento, sem markdown.

DOCUMENTO:
{conteudo_doc}"""

# ── Helpers ────────────────────────────────────────────────────────────────────
def carregar(path, default):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default

def salvar(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

def baixar_pdf(url):
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(r.content))
            return "\n".join(p.extract_text() or "" for p in reader.pages[:15])[:12000]
    except Exception as e:
        print(f"  ⚠️  PDF: {e}")
    return None

def gemini(prompt):
    r = requests.post(GEMINI_URL, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}
    }, timeout=60)
    if r.status_code == 200:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    print(f"  ❌ Gemini: {r.status_code}")
    return None

def get_tag(ticker):
    r = requests.get(f"{WP_API}/tags", params={"search": ticker}, headers=WP_HEADERS)
    tags = r.json()
    if tags:
        return tags[0]["id"]
    nova = requests.post(f"{WP_API}/tags", json={"name": ticker}, headers=WP_HEADERS).json()
    return nova.get("id")

def publicar(titulo, conteudo, categoria, ticker):
    tag_id = get_tag(ticker)
    r = requests.post(f"{WP_API}/posts", headers=WP_HEADERS, json={
        "title": titulo, "content": conteudo,
        "status": "publish", "categories": [categoria],
        "tags": [tag_id] if tag_id else []
    })
    if r.status_code in (200, 201):
        url = r.json()["link"]
        print(f"  ✅ {url}")
        return url
    print(f"  ❌ WP {r.status_code}: {r.text[:200]}")
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

# ── Processamento ──────────────────────────────────────────────────────────────
def processar(lista, controle, desde_data, tipo):
    label = "FIIs" if tipo == "fii" else "Ações"
    print(f"\n{'📦' if tipo=='fii' else '📈'} {label}...")
    
    for ativo in lista:
        t = ativo["ticker"]
        print(f"\n  → {t}")
        
        docs = buscar_docs_fii(t, desde_data) if tipo == "fii" else buscar_docs_acao(t, desde_data)
        if not docs:
            print("     Nenhum doc novo.")
            continue
        
        for doc in docs:
            key = f"{t}_{doc['data']}_{doc.get('tipo','')[:15]}"
            if key in controle:
                print(f"     Já processado.")
                continue
            
            print(f"     📄 {doc['titulo']}")
            texto = baixar_pdf(doc["url"]) if doc.get("url") else None
            if not texto:
                print("     ⚠️  Sem texto.")
                controle[key] = {"status": "erro_pdf"}
                salvar(CONTROLE, controle)
                continue
            
            print("     🤖 Gemini...")
            tmpl = PROMPT_FII if tipo == "fii" else PROMPT_ACAO
            if tipo == "fii":
                prompt = tmpl.format(ticker=t, nome=ativo["nome"], ri_url=ativo["ri_url"],
                                     tipo=ativo.get("tipo",""), gestora=ativo.get("gestora",""),
                                     conteudo_doc=texto)
            else:
                prompt = tmpl.format(ticker=t, nome=ativo["nome"], ri_url=ativo["ri_url"],
                                     setor=ativo.get("setor",""), conteudo_doc=texto)
            
            analise = gemini(prompt)
            if not analise:
                controle[key] = {"status": "erro_gemini"}
                salvar(CONTROLE, controle)
                continue
            
            titulo = f"{t} — {ativo['nome']} | {doc['titulo']}"
            cat = CAT_FIIS if tipo == "fii" else CAT_ACOES
            url = publicar(titulo, analise, cat, t)
            
            if url:
                atualizar_ranking(t, url, tipo)
                controle[key] = {"status": "ok", "url": url}
            else:
                controle[key] = {"status": "erro_wp"}
            
            salvar(CONTROLE, controle)

def main():
    print(f"🐟 Manjubinha — {datetime.today().strftime('%Y-%m-%d %H:%M UTC')}")
    config   = carregar("config.json", {})
    controle = carregar(CONTROLE, {})
    
    desde = datetime(2026, 6, 1) if not controle else datetime.today() - timedelta(days=8)
    print(f"   📅 Desde {desde.strftime('%Y-%m-%d')}")
    
    processar(config.get("fiis", []),  controle, desde, "fii")
    processar(config.get("acoes", []), controle, desde, "acao")
    print("\n✅ Concluído!")

if __name__ == "__main__":
    main()
