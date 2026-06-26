"""
Manjubinha Investidor — Análises Automáticas
Usa Claude Haiku (Anthropic) para analisar e publicar no WordPress.

Controle de cota:
- Modelo: claude-haiku-4-5 (~$0.80/MTok input, $4/MTok output)
- ~1.000 tokens entrada + ~1.200 saída por ativo = ~2.200 tok/ativo
- 60 ativos x 2.200 = ~132.000 tokens por execução
- 2x/semana x 4 semanas = ~1.05M tokens/mês -> dentro da cota
- Sleep de 3s entre chamadas (limite: 50 RPM no Haiku)
"""

import os, json, requests, time, base64
from datetime import datetime, timedelta
from pathlib import Path

# -- Config -------------------------------------------------------------------
WP_URL = "https://manjubinhainvestidor.com.br"
WP_USER = os.environ["WP_USER"]
WP_PASS = os.environ["WP_APP_PASS"]
CLAUDE_KEY = os.environ["ANTHROPIC_API_KEY"]

WP_API = WP_URL + "/wp-json/wp/v2"
_cred = base64.b64encode((WP_USER + ":" + WP_PASS).encode()).decode()
WP_HEADERS = {"Authorization": "Basic " + _cred}

CLAUDE_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_HEADERS = {
    "x-api-key": CLAUDE_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}
CLAUDE_MODEL = "claude-haiku-4-5"
MAX_TOKENS_OUT = 1200

CONTROLE = Path("controle_docs.json")
CAT_FIIS = None
CAT_ACOES = None

MES_ATUAL = datetime.today().strftime("%B de %Y")
MES_KEY = datetime.today().strftime("%m-%Y")

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
    r = requests.get(WP_API + "/categories", headers=WP_HEADERS, params={"slug": slug})
    cats = r.json()
    if isinstance(cats, list) and cats:
        return cats[0]["id"]
    r = requests.post(WP_API + "/categories", headers=WP_HEADERS, json={"name": name, "slug": slug})
    return r.json().get("id")

def get_or_create_tag(ticker):
    r = requests.get(WP_API + "/tags", headers=WP_HEADERS, params={"search": ticker})
    tags = r.json()
    if isinstance(tags, list) and tags:
        return tags[0]["id"]
    nova = requests.post(WP_API + "/tags", headers=WP_HEADERS, json={"name": ticker}).json()
    return nova.get("id")

def publicar(titulo, conteudo, categoria, ticker):
    tag_id = get_or_create_tag(ticker)
    r = requests.post(WP_API + "/posts", headers=WP_HEADERS, json={
        "title": titulo,
        "content": conteudo,
        "status": "publish",
        "categories": [categoria],
        "tags": [tag_id] if tag_id else [],
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

# -- Página de Ranking WordPress ----------------------------------------------

def build_ranking_html(ranking):
    fiis = json.dumps(ranking.get("fiis", []), ensure_ascii=False)
    acoes = json.dumps(ranking.get("acoes", []), ensure_ascii=False)
    ultima = ranking.get("ultima_atualizacao", "")
    proxima = ranking.get("proxima_atualizacao", "")
    html = (
        "<!-- wp:html -->\n"
        "<style>\n"
        ".mj-ranking{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#222}\n"
        ".mj-tabs{display:flex;gap:8px;margin-bottom:1.2rem}\n"
        ".mj-tab{padding:7px 22px;border:1px solid #d0d0d0;border-radius:8px;background:transparent;font-size:14px;cursor:pointer;color:#666}\n"
        ".mj-tab.active{background:#D95218;color:#fff;border-color:#D95218;font-weight:500}\n"
        ".mj-legend{display:flex;gap:18px;margin-bottom:.8rem;flex-wrap:wrap}\n"
        ".mj-leg{display:flex;align-items:center;gap:6px;font-size:12px;color:#888}\n"
        ".mj-dot{width:10px;height:10px;border-radius:50%}\n"
        ".mj-filters{display:flex;gap:6px;margin-bottom:.8rem;flex-wrap:wrap}\n"
        ".mj-fbtn{padding:4px 12px;border:1px solid #d0d0d0;border-radius:20px;background:transparent;font-size:12px;cursor:pointer;color:#888}\n"
        ".mj-fbtn.on{border-color:#D95218;color:#D95218;background:#fff5f2}\n"
        ".mj-wrap{overflow-x:auto}\n"
        ".mj-table{width:100%;border-collapse:collapse;font-size:13px;min-width:480px}\n"
        ".mj-table thead th{padding:8px 10px;text-align:left;color:#999;font-weight:500;border-bottom:1px solid #e5e5e5;font-size:11px;white-space:nowrap;text-transform:uppercase}\n"
        ".mj-table thead th.tc{text-align:center}\n"
        ".mj-table tbody tr{border-bottom:1px solid #f0f0f0}\n"
        ".mj-table tbody tr:hover{background:#fafafa}\n"
        ".mj-table td{padding:9px 10px}\n"
        ".mj-tk{font-weight:600;font-size:13px}\n"
        ".mj-tk a{color:#D95218;text-decoration:none}\n"
        ".mj-tk a:hover{text-decoration:underline}\n"
        ".mj-tk span{color:#D95218}\n"
        ".mj-nm{color:#999;font-size:12px}\n"
        ".mj-tag{font-size:11px;padding:2px 8px;border-radius:10px;background:#f5f5f5;color:#888}\n"
        ".mj-sc{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;font-size:12px;font-weight:500}\n"
        ".mj-sh{background:#EAF3DE;color:#3B6D11}\n"
        ".mj-sm{background:#FEF3D0;color:#92600A}\n"
        ".mj-sl{background:#FCEBEB;color:#A32D2D}\n"
        ".mj-tot{font-weight:600;font-size:14px}\n"
        ".mj-rk{color:#bbb;font-size:12px}\n"
        ".mj-badge{font-size:10px;background:#D95218;color:#fff;padding:1px 6px;border-radius:4px;margin-left:4px}\n"
        ".mj-upd{font-size:11px;color:#bbb;text-align:right;margin-top:.8rem}\n"
        "</style>\n"
        "<div class=\"mj-ranking\">\n"
        "<div class=\"mj-tabs\">\n"
        "<button class=\"mj-tab active\" onclick=\"mjShow('fii',this)\">FIIs — Top 30</button>\n"
        "<button class=\"mj-tab\" onclick=\"mjShow('ac',this)\">Ações — Top 30</button>\n"
        "</div>\n"
        "<div class=\"mj-legend\">\n"
        "<span class=\"mj-leg\"><span class=\"mj-dot\" style=\"background:#639922\"></span>8-10 alto</span>\n"
        "<span class=\"mj-leg\"><span class=\"mj-dot\" style=\"background:#BA7517\"></span>5-7 médio</span>\n"
        "<span class=\"mj-leg\"><span class=\"mj-dot\" style=\"background:#E24B4A\"></span>1-4 baixo</span>\n"
        "</div>\n"
        "<div id=\"mj-fii-panel\">\n"
        "<div class=\"mj-filters\" id=\"mj-fii-filters\"></div>\n"
        "<div class=\"mj-wrap\"><table class=\"mj-table\">\n"
        "<thead><tr><th class=\"mj-rk\">#</th><th>Ticker</th><th>Nome</th><th>Tipo</th>"
        "<th class=\"tc\">Perene</th><th class=\"tc\">Renda</th><th class=\"tc\">Valor</th><th class=\"tc\">Liq</th><th class=\"tc\">Nota</th>"
        "</tr></thead>\n"
        "<tbody id=\"mj-fii-body\"></tbody>\n"
        "</table></div></div>\n"
        "<div id=\"mj-ac-panel\" style=\"display:none\">\n"
        "<div class=\"mj-filters\" id=\"mj-ac-filters\"></div>\n"
        "<div class=\"mj-wrap\"><table class=\"mj-table\">\n"
        "<thead><tr><th class=\"mj-rk\">#</th><th>Ticker</th><th>Nome</th><th>Setor</th>"
        "<th class=\"tc\">Perene</th><th class=\"tc\">Renda</th><th class=\"tc\">Valor</th><th class=\"tc\">Liq</th><th class=\"tc\">Nota</th>"
        "</tr></thead>\n"
        "<tbody id=\"mj-ac-body\"></tbody>\n"
        "</table></div></div>\n"
        "<div class=\"mj-upd\" id=\"mj-upd-info\"></div>\n"
        "</div>\n"
        "<script>\n"
        "(function(){\n"
        "var FII_DATA=" + fiis + ";\n"
        "var AC_DATA=" + acoes + ";\n"
        "var ULT='" + ultima + "';\n"
        "var PROX='" + proxima + "';\n"
        "document.getElementById('mj-upd-info').textContent='Última atualização: '+ULT+' · Próxima: '+PROX;\n"
        "function sc(v){return v>=8?'mj-sh':v>=5?'mj-sm':'mj-sl';}\n"
        "function renderTable(id,data,key){\n"
        "var sorted=[].concat(data).sort(function(a,b){return b.nota-a.nota;});\n"
        "document.getElementById(id).innerHTML=sorted.map(function(d,i){\n"
        "var tick=d.post_url?'<a href=\"'+d.post_url+'\" target=\"_blank\">'+d.ticker+'</a>':'<span>'+d.ticker+'</span>';\n"
        "var badge=d.post_url?'<span class=\"mj-badge\">análise</span>':'';\n"
        "return '<tr data-tipo=\"'+d[key]+'\"><td class=\"mj-rk\">'+(i+1)+'</td><td class=\"mj-tk\">'+tick+badge+'</td><td class=\"mj-nm\">'+d.nome+'</td><td><span class=\"mj-tag\">'+d[key]+'</span></td><td class=\"tc\"><span class=\"mj-sc '+sc(d.perene)+'\">'+d.perene+'</span></td><td class=\"tc\"><span class=\"mj-sc '+sc(d.renda)+'\">'+d.renda+'</span></td><td class=\"tc\"><span class=\"mj-sc '+sc(d.valorizacao)+'\">'+d.valorizacao+'</span></td><td class=\"tc\"><span class=\"mj-sc '+sc(d.liquidez)+'\">'+d.liquidez+'</span></td><td class=\"tc mj-tot\">'+d.nota.toFixed(1)+'</td></tr>';\n"
        "}).join('');\n"
        "}\n"
        "function buildFilters(panel,data,key){\n"
        "var tipos=['Todos'].concat(data.reduce(function(acc,d){if(!acc.includes(d[key]))acc.push(d[key]);return acc;},[]));"
        "document.getElementById('mj-'+panel+'-filters').innerHTML=tipos.map(function(t,i){"
        "return '<button class=\"mj-fbtn'+(i===0?' on':'')+'\" onclick=\"mjFilter(\\'+panel+'\\'+',' + "'" + "'" + '+t+' + "'" + "'" + '+this)\">'+t+'</button>';"
        "}).join('');\n"
        "}\n"
        "buildFilters('fii',FII_DATA,'tipo');\n"
        "buildFilters('ac',AC_DATA,'setor');\n"
        "renderTable('mj-fii-body',FII_DATA,'tipo');\n"
        "renderTable('mj-ac-body',AC_DATA,'setor');\n"
        "})();\n"
        "window.mjFilter=function(panel,tipo,btn){"
        "document.querySelectorAll('#mj-'+panel+'-filters .mj-fbtn').forEach(function(b){b.classList.remove('on');});"
        "btn.classList.add('on');"
        "var n=1;"
        "document.querySelectorAll('#mj-'+panel+'-body tr').forEach(function(r){"
        "var show=tipo==='Todos'||r.dataset.tipo===tipo;"
        "r.style.display=show?'':'none';"
        "if(show)r.querySelector('.mj-rk').textContent=n++;"
        "});"
        "};\n"
        "window.mjShow=function(which,btn){"
        "document.getElementById('mj-fii-panel').style.display=which==='fii'?'':'none';"
        "document.getElementById('mj-ac-panel').style.display=which==='ac'?'':'none';"
        "document.querySelectorAll('.mj-tab').forEach(function(t){t.classList.remove('active');});"
        "btn.classList.add('active');"
        "};\n"
        "</script>\n"
        "<!-- /wp:html -->"
    )
    return html


def publicar_pagina_ranking(ranking):
    print("")
    print("Publicando pagina de ranking no WordPress...")
    html = build_ranking_html(ranking)
    slug = "ranking-de-ativos"
    r = requests.get(WP_API + "/pages", headers=WP_HEADERS, params={"slug": slug})
    pages = r.json()
    payload = {
        "title": "Ranking de Ativos",
        "content": html,
        "status": "publish",
        "slug": slug,
    }
    if isinstance(pages, list) and pages:
        page_id = pages[0]["id"]
        r2 = requests.post(WP_API + "/pages/" + str(page_id), headers=WP_HEADERS, json=payload)
        if r2.status_code in (200, 201):
            print("  Pagina de ranking ATUALIZADA: " + r2.json().get("link", ""))
        else:
            print("  Erro ao atualizar pagina: " + str(r2.status_code) + " " + r2.text[:200])
    else:
        r2 = requests.post(WP_API + "/pages", headers=WP_HEADERS, json=payload)
        if r2.status_code in (200, 201):
            print("  Pagina de ranking CRIADA: " + r2.json().get("link", ""))
        else:
            print("  Erro ao criar pagina: " + str(r2.status_code) + " " + r2.text[:200])


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
    config = carregar("config.json", {})
    controle = carregar(CONTROLE, {})
    global CAT_FIIS, CAT_ACOES
    CAT_FIIS = get_or_create_category("analises-fiis", "FIIs | Analises")
    CAT_ACOES = get_or_create_category("documentos-acoes", "Acoes | Analises")
    print("  FIIs: " + str(CAT_FIIS) + " | Acoes: " + str(CAT_ACOES))
    print("  Mes: " + MES_ATUAL)
    processar(config.get("fiis", []), controle, MES_KEY, MES_ATUAL, "fii")
    processar(config.get("acoes", []), controle, MES_KEY, MES_ATUAL, "acao")
    ranking = carregar("ranking.json", {})
    publicar_pagina_ranking(ranking)
    print("")
    print("Concluido!")

if __name__ == "__main__":
    main()
