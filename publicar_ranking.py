"""
Manjubinha Investidor - Publica/Atualiza a pagina de Ranking no WordPress
Script independente: nao precisa da API Anthropic.
Le ranking.json e cria/atualiza a pagina wp em /ranking-de-ativos/.
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
    fiis_json = json.dumps(ranking.get("fiis", []), ensure_ascii=False)
    acoes_json = json.dumps(ranking.get("acoes", []), ensure_ascii=False)
    ultima = ranking.get("ultima_atualizacao", "")
    proxima = ranking.get("proxima_atualizacao", "")

    css = (
        "<style>"
        ".mjr{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;color:#222}"
        ".mjt{display:flex;gap:8px;margin-bottom:1.2rem}"
        ".mjb{padding:7px 22px;border:1px solid #d0d0d0;border-radius:8px;background:transparent;font-size:14px;cursor:pointer;color:#666}"
        ".mjb.on{background:#D95218;color:#fff;border-color:#D95218;font-weight:500}"
        ".mjl{display:flex;gap:18px;margin-bottom:.8rem;flex-wrap:wrap}"
        ".mjli{display:flex;align-items:center;gap:6px;font-size:12px;color:#888}"
        ".mjd{width:10px;height:10px;border-radius:50%;display:inline-block}"
        ".mjf{display:flex;gap:6px;margin-bottom:.8rem;flex-wrap:wrap}"
        ".mjfb{padding:4px 12px;border:1px solid #d0d0d0;border-radius:20px;background:transparent;font-size:12px;cursor:pointer;color:#888}"
        ".mjfb.on{border-color:#D95218;color:#D95218;background:#fff5f2}"
        ".mjw{overflow-x:auto}"
        ".mjtbl{width:100%;border-collapse:collapse;font-size:13px;min-width:480px}"
        ".mjtbl thead th{padding:8px 10px;text-align:left;color:#999;font-weight:500;border-bottom:1px solid #e5e5e5;font-size:11px;white-space:nowrap;text-transform:uppercase}"
        ".mjtbl thead th.tc{text-align:center}"
        ".mjtbl tbody tr{border-bottom:1px solid #f0f0f0}"
        ".mjtbl tbody tr:hover{background:#fafafa}"
        ".mjtbl td{padding:9px 10px}"
        ".mjk{font-weight:600;font-size:13px}"
        ".mjk a{color:#D95218;text-decoration:none}"
        ".mjk a:hover{text-decoration:underline}"
        ".mjk span{color:#D95218}"
        ".mjnm{color:#999;font-size:12px}"
        ".mjtag{font-size:11px;padding:2px 8px;border-radius:10px;background:#f5f5f5;color:#888}"
        ".mjsc{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;font-size:12px;font-weight:500}"
        ".mjsh{background:#EAF3DE;color:#3B6D11}"
        ".mjsm{background:#FEF3D0;color:#92600A}"
        ".mjsl{background:#FCEBEB;color:#A32D2D}"
        ".mjtot{font-weight:600;font-size:14px}"
        ".mjrk{color:#bbb;font-size:12px}"
        ".mjbdg{font-size:10px;background:#D95218;color:#fff;padding:1px 6px;border-radius:4px;margin-left:4px}"
        ".mjupd{font-size:11px;color:#bbb;text-align:right;margin-top:.8rem}"
        "</style>"
    )

    html_struct = (
        '<div class="mjr">'
        '<div class="mjt">'
        '<button class="mjb on" onclick="mjShow(this,1)">FIIs &#8212; Top 30</button>'
        '<button class="mjb" onclick="mjShow(this,2)">Ações &#8212; Top 30</button>'
        '</div>'
        '<div class="mjl">'
        '<span class="mjli"><span class="mjd" style="background:#639922"></span>8-10 alto</span>'
        '<span class="mjli"><span class="mjd" style="background:#BA7517"></span>5-7 médio</span>'
        '<span class="mjli"><span class="mjd" style="background:#E24B4A"></span>1-4 baixo</span>'
        '</div>'
        '<div id="mjp1">'
        '<div class="mjf" id="mjf1"></div>'
        '<div class="mjw"><table class="mjtbl"><thead><tr>'
        '<th class="mjrk">#</th><th>Ticker</th><th>Nome</th><th>Tipo</th>'
        '<th class="tc">Perene</th><th class="tc">Renda</th><th class="tc">Valor</th><th class="tc">Liq</th><th class="tc">Nota</th>'
        '</tr></thead><tbody id="mjb1"></tbody></table></div>'
        '</div>'
        '<div id="mjp2" style="display:none">'
        '<div class="mjf" id="mjf2"></div>'
        '<div class="mjw"><table class="mjtbl"><thead><tr>'
        '<th class="mjrk">#</th><th>Ticker</th><th>Nome</th><th>Setor</th>'
        '<th class="tc">Perene</th><th class="tc">Renda</th><th class="tc">Valor</th><th class="tc">Liq</th><th class="tc">Nota</th>'
        '</tr></thead><tbody id="mjb2"></tbody></table></div>'
        '</div>'
        '<div class="mjupd" id="mjupd"></div>'
        '</div>'
    )

    js = (
        "<script>"
        "(function(){"
        "var D1=" + fiis_json + ";"
        "var D2=" + acoes_json + ";"
        "document.getElementById('mjupd').textContent='Ultima atualizacao: " + ultima + " - Proxima: " + proxima + "';"
        "function sc(v){return v>=8?'mjsh':v>=5?'mjsm':'mjsl';}"
        "function row(d,i,k){"
        "var lnk=d.post_url?('<a href='+JSON.stringify(d.post_url)+' target=_blank>'+d.ticker+'</a>'):'<span>'+d.ticker+'</span>';"
        "var bdg=d.post_url?'<span class=mjbdg>analise</span>':'';"
        "return '<tr data-t='+JSON.stringify(d[k])+'><td class=mjrk>'+(i+1)+'</td><td class=mjk>'+lnk+bdg+'</td><td class=mjnm>'+d.nome+'</td><td><span class=mjtag>'+d[k]+'</span></td><td class=tc><span class="mjsc '+sc(d.perene)+'">'+d.perene+'</span></td><td class=tc><span class="mjsc '+sc(d.renda)+'">'+d.renda+'</span></td><td class=tc><span class="mjsc '+sc(d.valorizacao)+'">'+d.valorizacao+'</span></td><td class=tc><span class="mjsc '+sc(d.liquidez)+'">'+d.liquidez+'</span></td><td class="tc mjtot">'+d.nota.toFixed(1)+'</td></tr>';"
        "}"
        "function render(bid,data,key){"
        "var s=data.slice().sort(function(a,b){return b.nota-a.nota;});"
        "document.getElementById(bid).innerHTML=s.map(function(d,i){return row(d,i,key);}).join('');"
        "}"
        "function filters(fid,bid,data,key){"
        "var tp=['Todos'].concat(data.reduce(function(a,d){if(a.indexOf(d[key])<0)a.push(d[key]);return a;},[]));"
        "document.getElementById(fid).innerHTML=tp.map(function(t,i){"
        "return '<button class=mjfb'+(i===0?' on':'')+' onclick=mjF(this,'+JSON.stringify(bid)+','+JSON.stringify(t)+')>'+t+'</button>';"
        "}).join('');"
        "}"
        "render('mjb1',D1,'tipo');render('mjb2',D2,'setor');"
        "filters('mjf1','mjb1',D1,'tipo');filters('mjf2','mjb2',D2,'setor');"
        "})();"
        "function mjF(btn,bid,tipo){"
        "var p=btn.closest('.mjf');"
        "p.querySelectorAll('.mjfb').forEach(function(b){b.classList.remove('on');});"
        "btn.classList.add('on');"
        "var n=1;"
        "document.getElementById(bid).querySelectorAll('tr').forEach(function(r){"
        "var ok=tipo==='Todos'||r.dataset.t===tipo;"
        "r.style.display=ok?'':'none';"
        "if(ok)r.querySelector('.mjrk').textContent=n++;"
        "});"
        "}"
        "function mjShow(btn,panel){"
        "document.getElementById('mjp1').style.display=panel===1?'':'none';"
        "document.getElementById('mjp2').style.display=panel===2?'':'none';"
        "document.querySelectorAll('.mjt .mjb').forEach(function(b){b.classList.remove('on');});"
        "btn.classList.add('on');"
        "}"
        "</script>"
    )

    return "<!-- wp:html -->" + css + html_struct + js + "<!-- /wp:html -->"


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
