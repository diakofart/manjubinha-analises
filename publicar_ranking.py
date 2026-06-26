"""
Manjubinha Investidor — Publica/Atualiza a página de Ranking no WordPress
Script independente: não precisa da API Anthropic.
Lê ranking.json e cria/atualiza a página wp em /ranking-de-ativos/.
"""

import os, json, requests, base64
from pathlib import Path

WP_URL = "https://manjubinhainvestidor.com.br"
WP_USER = os.environ["WP_USER"]
WP_PASS = os.environ["WP_APP_PASS"]

WP_API = WP_URL + "/wp-json/wp/v2"
_cred = base64.b64encode((WP_USER + ":" + WP_PASS).encode()).decode()
WP_HEADERS = {"Authorization": "Basic " + _cred}


def carregar(path, default):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default


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
        "<button class=\"mj-tab active\" onclick=\"mjShow('fii',this)\">FIIs &#8212; Top 30</button>\n"
        "<button class=\"mj-tab\" onclick=\"mjShow('ac',this)\">Ações &#8212; Top 30</button>\n"
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
        "document.getElementById('mj-upd-info').textContent='Última atualização: " + ultima + " \u00b7 Próxima: " + proxima + "';\n"
        "function sc(v){return v>=8?'mj-sh':v>=5?'mj-sm':'mj-sl';}\n"
        "function renderTable(id,data,key){\n"
        "var s=[].concat(data).sort(function(a,b){return b.nota-a.nota;});\n"
        "document.getElementById(id).innerHTML=s.map(function(d,i){\n"
        "var lnk=d.post_url?'<a href=\"'+d.post_url+'\" target=\"_blank\">'+d.ticker+'</a>':'<span>'+d.ticker+'</span>';\n"
        "var bdg=d.post_url?'<span class=\"mj-badge\">análise</span>':'';\n"
        "return '<tr data-tipo=\"'+d[key]+'\"><td class=\"mj-rk\">'+(i+1)+'</td><td class=\"mj-tk\">'+lnk+bdg+'</td><td class=\"mj-nm\">'+d.nome+'</td><td><span class=\"mj-tag\">'+d[key]+'</span></td><td class=\"tc\"><span class=\"mj-sc '+sc(d.perene)+'\">'+d.perene+'</span></td><td class=\"tc\"><span class=\"mj-sc '+sc(d.renda)+'\">'+d.renda+'</span></td><td class=\"tc\"><span class=\"mj-sc '+sc(d.valorizacao)+'\">'+d.valorizacao+'</span></td><td class=\"tc\"><span class=\"mj-sc '+sc(d.liquidez)+'\">'+d.liquidez+'</span></td><td class=\"tc mj-tot\">'+d.nota.toFixed(1)+'</td></tr>';\n"
        "}).join('');\n"
        "}\n"
        "function buildFilters(panel,data,key){\n"
        "var tp=['Todos'].concat(data.reduce(function(a,d){if(a.indexOf(d[key])<0)a.push(d[key]);return a;},[]));"
        "document.getElementById('mj-'+panel+'-filters').innerHTML=tp.map(function(t,i){"
        "return '<button class=\"mj-fbtn'+(i===0?' on':'')+'\" onclick=\"mjFlt(\''+panel+'\',\''+t+'\',this)\">'+t+'</button>';"
        "}).join('');\n"
        "}\n"
        "buildFilters('fii',FII_DATA,'tipo');\n"
        "buildFilters('ac',AC_DATA,'setor');\n"
        "renderTable('mj-fii-body',FII_DATA,'tipo');\n"
        "renderTable('mj-ac-body',AC_DATA,'setor');\n"
        "})();\n"
        "window.mjFlt=function(p,t,b){"
        "document.querySelectorAll('#mj-'+p+'-filters .mj-fbtn').forEach(function(x){x.classList.remove('on');});"
        "b.classList.add('on');var n=1;"
        "document.querySelectorAll('#mj-'+p+'-body tr').forEach(function(r){"
        "var s=t==='Todos'||r.dataset.tipo===t;r.style.display=s?'':'none';"
        "if(s)r.querySelector('.mj-rk').textContent=n++;});};\n"
        "window.mjShow=function(w,b){"
        "document.getElementById('mj-fii-panel').style.display=w==='fii'?'':'none';"
        "document.getElementById('mj-ac-panel').style.display=w==='ac'?'':'none';"
        "document.querySelectorAll('.mj-tab').forEach(function(t){t.classList.remove('active');});"
        "b.classList.add('active');};\n"
        "</script>\n"
        "<!-- /wp:html -->"
    )
    return html


def publicar_pagina_ranking(ranking):
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
        pid = pages[0]["id"]
        r2 = requests.post(WP_API + "/pages/" + str(pid), headers=WP_HEADERS, json=payload)
        if r2.status_code in (200, 201):
            print("Pagina ATUALIZADA: " + r2.json().get("link", ""))
            return r2.json().get("link", "")
        else:
            print("Erro ao atualizar: " + str(r2.status_code) + " " + r2.text[:300])
    else:
        r2 = requests.post(WP_API + "/pages", headers=WP_HEADERS, json=payload)
        if r2.status_code in (200, 201):
            print("Pagina CRIADA: " + r2.json().get("link", ""))
            return r2.json().get("link", "")
        else:
            print("Erro ao criar: " + str(r2.status_code) + " " + r2.text[:300])
    return None


if __name__ == "__main__":
    ranking = carregar("ranking.json", {})
    publicar_pagina_ranking(ranking)
