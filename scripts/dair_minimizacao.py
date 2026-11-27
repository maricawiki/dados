"""Minimização de dados DAIR para disponibilização pública.
CNPJ válido de fundo não é identificador de conta; demais identificações são
substituídas por rótulos locais à competência, nunca chaves de rastreamento.
"""
import re

CASH="Disponibilidades Financeiras"
NUMERIC=re.compile(r"[0-9][0-9 ./-]{6,}[0-9]")

def valid_cnpj(value):
    if not re.fullmatch(r"[0-9]{14}",value) or len(set(value))==1:
        return False
    digits=list(map(int,value))
    for n,weights in [(12,[5,4,3,2,9,8,7,6,5,4,3,2]),(13,[6,5,4,3,2,9,8,7,6,5,4,3,2])]:
        rem=sum(digits[i]*w for i,w in enumerate(weights))%11
        if digits[n]!=(0 if rem<2 else 11-rem):
            return False
    return True

def sanitize_positions(positions):
    cash_count=asset_count=0
    result=[]
    for row in positions:
        p={k:row[k] for k in ("segmento","tipo_ativo","id_ativo","nome_ativo","valor_centavos","linhas")}
        if p["segmento"]==CASH:
            cash_count+=1
            n=f"{cash_count:03d}"
            p.update(id_ativo="DISP-"+n,nome_ativo="Disponibilidade financeira "+n)
        elif not valid_cnpj(p["id_ativo"]):
            asset_count+=1
            n=f"{asset_count:03d}"
            p.update(id_ativo="ATIVO-"+n,nome_ativo="Ativo de investimento "+n)
        elif NUMERIC.search(p["nome_ativo"]):
            p["nome_ativo"]="Fundo de investimento (CNPJ informado)"
        result.append(p)
    return sorted(result,key=lambda p:(-p["valor_centavos"],p["segmento"],p["id_ativo"]))

def validate_position(p):
    if set(p)!={"segmento","tipo_ativo","id_ativo","nome_ativo","valor_centavos","linhas"}:
        raise ValueError("Campos inesperados")
    i=p["id_ativo"]; n=p["nome_ativo"]
    if p["segmento"]==CASH:
        if not re.fullmatch(r"DISP-[0-9]{3}",i) or n!="Disponibilidade financeira "+i[5:]:
            raise ValueError("Identificação de disponibilidade não minimizada")
    elif not valid_cnpj(i):
        if not re.fullmatch(r"ATIVO-[0-9]{3}",i) or n!="Ativo de investimento "+i[6:]:
            raise ValueError("Identificação de ativo não minimizada")
    elif NUMERIC.search(n):
        raise ValueError("Sequência numérica não revisada no nome do fundo")
    if type(p["valor_centavos"]) is not int or p["valor_centavos"]<=0 or type(p["linhas"]) is not int or p["linhas"]<1:
        raise ValueError("Valor ou contagem inválida")
