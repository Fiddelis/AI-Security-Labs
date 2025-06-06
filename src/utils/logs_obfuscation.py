import pandas as pd
import glob
import re
import random

# Lista de termos a ofuscar
users = [
    'admin', 'root', 'guest', 'art-test', 'test', 'default',
    'administrator', 'superuser', 'sysadmin'
]
tools = [
    'BloodHound', 'SharpHound', 'redcanaryco', re.compile(r'[aA]tomic[\w -]*'),
    'mimikatz', 'nmap', 'cobaltstrike', 'ExternalPayloads',
    re.compile('_timestomp'), re.compile(r'r\d{3,}'), 'Folder_to_zip'
]
passwords = [
    re.compile(r'Password123\!'), '123456', 'admin123', 'qwerty', 'letmein',
    'passw0rd', '12345678', 'toor', re.compile(r'-4RTisCool!-321')
]
mitre = [re.compile(r"T\d{4}\.\d{3}"), re.compile(r"T\d{4}")]

ofuscation = users + tools + passwords + mitre

# Prefixos e sufixos para gerar nomes aleatórios
prefixos = [
    "modulo", "componente", "estrutura", "registro", "entrada",
    "elemento", "tarefa", "pacote", "unidade", "objeto"
]
sufixos = [
    "base", "padrao", "logico", "comum", "principal",
    "secundario", "auxiliar", "temporario", "ativo", "geral"
]

# Dicionário global que armazenará, para cada termo original,
# a string gerada aleatoriamente na primeira vez em que ele aparece.
obfuscation_map = {}

def random_words(text_original):
    """
    Gera uma combinação aleatória de prefixo_sufixo.
    O parâmetro `text_original` é apenas para manter a assinatura
    e possibilitar futuras customizações caso queira usar parte
    do termo original na lógica de geração.
    """
    return f"{random.choice(prefixos)}_{random.choice(sufixos)}"

def get_or_create_obfuscated(orig):
    """
    Retorna o valor ofuscado já existente em `obfuscation_map` para `orig`.
    Se não existir, gera um novo via random_words, armazena e retorna.
    """
    if orig not in obfuscation_map:
        obfuscation_map[orig] = random_words(orig)
    return obfuscation_map[orig]

def apply_obfuscation(text, terms):
    """
    Recebe um texto e uma lista de termos (strings ou padrões regex).
    Para cada termo, faz a substituição no texto, garantindo que
    ocorrências iguais sejam sempre trocadas pelo mesmo valor.
    """
    text = str(text)

    for term in terms:
        if isinstance(term, re.Pattern):
            # Para padrões regex, usamos term.sub com lambda que chama get_or_create_obfuscated(m.group())
            text = term.sub(lambda m: get_or_create_obfuscated(m.group()), text).replace('\\\\', '\\')
        else:
            # Para strings exatas, usamos \b...\b para trocar somente palavras inteiras
            padrao = r'\b' + re.escape(term) + r'\b'
            text = re.sub(padrao, lambda m: get_or_create_obfuscated(m.group()), text)
    return text

# Processo principal: percorre todos os arquivos .jsonl e aplica ofuscação
jsonl_files = glob.glob("attacks/*.jsonl")
for file in jsonl_files:
    df = pd.read_json(file, lines=True)

    for column in df.columns:
        df[column] = df[column].apply(lambda x: apply_obfuscation(x, ofuscation))

    new_file = file.replace("events", "events_processed")
    df.to_json(new_file, orient="records", lines=True, force_ascii=False)
