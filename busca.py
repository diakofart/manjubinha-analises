"""
Módulo de busca de documentos — FundosNet e CVM Open Data
"""

import requests
import csv
import io
from datetime import datetime

TIMEOUT = 20

def buscar_docs_fii(ticker, desde_data):
    """
    Busca documentos de FIIs no FundosNet usando busca geral por período,
    depois filtra pelo ticker no resultado.
    """
    docs = []
    tipos_relevantes = ["Relatório Mensal", "Fato Relevante", "Informe Mensal", "Comunicado"]
    
    try:
        # Busca documentos do período sem filtro de CNPJ
        url = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarDocumentos"
        params = {
            "tipoFundo": "FII",
            "dataInicial": desde_data.strftime("%Y-%m-%d"),
            "dataFinal": datetime.today().strftime("%Y-%m-%d"),
            "pagina": 0,
            "tamanhoPagina": 200,
        }
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            lista = data.get("data", {}).get("list", []) or data.get("list", [])
            for doc in lista:
                # Filtra pelo ticker
                codigo = (
                    doc.get("codigoFundo", "") or
                    doc.get("ticker", "") or
                    doc.get("siglaFundo", "")
                ).upper()
                if ticker not in codigo:
                    continue
                tipo = doc.get("tipoDocumento", {}).get("descricao", "") if isinstance(doc.get("tipoDocumento"), dict) else str(doc.get("tipoDocumento", ""))
                if not any(t in tipo for t in tipos_relevantes):
                    continue
                doc_id = doc.get("id", "")
                docs.append({
                    "titulo": f"{tipo} — {doc.get('competencia', doc.get('dataReferencia', ''))}",
                    "url": f"https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={doc_id}",
                    "data": str(doc.get("dataEntrega", ""))[:10],
                    "tipo": tipo
                })
    except Exception as e:
        print(f"  ⚠️  Erro FundosNet {ticker}: {e}")
    
    return docs


def buscar_docs_acao(ticker, desde_data):
    """
    Busca documentos de Ações no CVM Open Data (dados.cvm.gov.br).
    Usa os arquivos CSV públicos de ITR (resultado trimestral).
    """
    docs = []
    ano = desde_data.year
    
    # Mapeia ticker para código CVM (CNPJ raiz — usamos busca por nome)
    # O CSV de ITR contém: CNPJ_CIA, DT_REFER, DT_RECEB, LINK_DOC
    urls_csv = [
        f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_{ano}.csv",
        f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_{ano}.csv",
    ]
    
    # Nome da empresa por ticker (busca parcial no campo DENOM_CIA)
    nomes_busca = {
        "PETR4": "PETROLEO BRAS",
        "VALE3": "VALE S",
        "ITUB4": "ITAU UNIBANCO",
        "BBAS3": "BANCO DO BRASIL",
        "WEGE3": "WEG S",
        "BBDC4": "BANCO BRADESCO",
        "ABEV3": "AMBEV",
        "TAEE11": "TRANSMISSORA ALIANCA",
        "CPLE6": "COPEL",
        "EGIE3": "ENGIE BRASIL",
        "VIVT3": "TELEFONICA",
        "PRIO3": "PRIO",
        "SBSP3": "SABESP",
        "RDOR3": "REDE D OR",
        "B3SA3": "B3 S",
        "SUZB3": "SUZANO",
        "ENGI11": "ENERGISA",
        "CPFE3": "CPFL",
        "TOTS3": "TOTVS",
        "JBSS3": "JBS",
        "ALUP11": "ALUPAR",
        "KLBN11": "KLABIN",
        "BPAC11": "BANCO BTG",
        "EMBR3": "EMBRAER",
        "RENT3": "LOCALIZA",
        "CSAN3": "COSAN",
        "HAPV3": "HAPVIDA",
        "POMO4": "MARCOPOLO",
        "ALLL3": "RUMO",
        "IRBR3": "IRB BRASIL",
    }
    
    nome_busca = nomes_busca.get(ticker, ticker[:4])
    
    for url_csv in urls_csv:
        try:
            resp = requests.get(url_csv, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
            
            # CSV separado por ; com encoding latin-1
            conteudo = resp.content.decode("latin-1")
            reader = csv.DictReader(io.StringIO(conteudo), delimiter=";")
            
            for row in reader:
                nome = row.get("DENOM_CIA", "").upper()
                if nome_busca.upper() not in nome:
                    continue
                
                dt_receb = row.get("DT_RECEB", "")[:10]
                if dt_receb < desde_data.strftime("%Y-%m-%d"):
                    continue
                
                link = row.get("LINK_DOC", "")
                tipo = "ITR" if "itr" in url_csv else "DFP"
                dt_refer = row.get("DT_REFER", "")[:7]  # YYYY-MM
                
                docs.append({
                    "titulo": f"{tipo} — {dt_refer}",
                    "url": link,
                    "data": dt_receb,
                    "tipo": tipo,
                    "nome_empresa": row.get("DENOM_CIA", "")
                })
            
            if docs:
                break  # Achou no primeiro CSV, não precisa do segundo
                
        except Exception as e:
            print(f"  ⚠️  Erro CVM Open Data {ticker}: {e}")
    
    return docs
