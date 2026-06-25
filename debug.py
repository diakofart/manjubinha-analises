"""
Script de diagnóstico — verifica o que FundosNet e CVM retornam
"""
import requests
import json
from datetime import datetime

DESDE = "2026-06-01"
HOJE  = datetime.today().strftime("%Y-%m-%d")

print("=" * 60)
print("1. TESTANDO FUNDOSNET")
print("=" * 60)

try:
    url = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarDocumentos"
    params = {
        "tipoFundo": "FII",
        "dataInicial": DESDE,
        "dataFinal": HOJE,
        "pagina": 0,
        "tamanhoPagina": 5,
    }
    r = requests.get(url, params=params, timeout=30)
    print(f"Status: {r.status_code}")
    print(f"Primeiros 2000 chars da resposta:")
    print(r.text[:2000])
except Exception as e:
    print(f"ERRO: {e}")

print("\n" + "=" * 60)
print("2. TESTANDO CVM OPEN DATA — ITR 2026")
print("=" * 60)

try:
    url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_2026.csv"
    r = requests.get(url, timeout=20)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        linhas = r.text.split("\n")
        print(f"Total de linhas: {len(linhas)}")
        print(f"Header: {linhas[0]}")
        print(f"Primeiras 3 linhas de dados:")
        for l in linhas[1:4]:
            print(l)
    else:
        print(r.text[:500])
except Exception as e:
    print(f"ERRO: {e}")

print("\n" + "=" * 60)
print("3. TESTANDO CVM — LISTA DE ARQUIVOS DISPONÍVEIS")
print("=" * 60)

try:
    url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/"
    r = requests.get(url, timeout=20)
    print(f"Status: {r.status_code}")
    print(r.text[:1000])
except Exception as e:
    print(f"ERRO: {e}")

print("\n" + "=" * 60)
print("4. TESTANDO CVM — ITR 2025 (fallback)")
print("=" * 60)

try:
    url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_2025.csv"
    r = requests.get(url, timeout=20)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        linhas = r.content.decode("latin-1").split("\n")
        print(f"Total de linhas: {len(linhas)}")
        print(f"Header: {linhas[0]}")
        # Busca Petrobras como teste
        petro = [l for l in linhas if "PETROLEO" in l.upper()][:2]
        print(f"Linhas com PETROLEO: {len([l for l in linhas if 'PETROLEO' in l.upper()])}")
        for l in petro:
            print(l[:200])
except Exception as e:
    print(f"ERRO: {e}")
