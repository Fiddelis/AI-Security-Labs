import pandas as pd
import glob
import re
import random

users = [
    'admin', 'root', 'guest', 'art-test', 'test', 'default',
    'administrator', 'superuser', 'sysadmin'
]
tools = [
    'redcanaryco', re.compile(r'[aA]tomic[\w -]*'), 'mimikatz', 'nmap', 'cobaltstrike', 'metasploit', 'ExternalPayloads', re.compile('_timestomp'), re.compile(r'r\d{3,}'), 'Folder_to_zip'
]
passwords = [
    re.compile(r'Password123\!'), '123456', 'admin123', 'qwerty', 'letmein',
    'passw0rd', '12345678', 'toor', re.compile(r'-4RTisCool!-321')
]
mitre = [re.compile(r"T\d{4}\.\d{3}"), re.compile(r"T\d{4}")]

ofuscation = users + tools + passwords + mitre

prefixos = [
    "modulo", "componente", "estrutura", "registro", "entrada", "elemento", "tarefa", "pacote", "unidade", "objeto"
]

sufixos = [
    "base", "padrao", "logico", "comum", "principal", "secundario", "auxiliar", "temporario", "ativo", "geral"
]
def random_words(text):
    text = str(text)
    
    return f"{random.choice(prefixos)}_{random.choice(sufixos)}"

def apply_obfuscation(text, terms):
    text = str(text)

    for term in terms:
        if isinstance(term, re.Pattern):
            # Aplica a substituição para o padrão regex
            text = term.sub(lambda m: random_words(m.group()), text).replace('\\\\', '\\')
        else:
            # Cria um padrão com limites de palavra para substituir termos completos
            padrao = r'\b' + re.escape(term) + r'\b'
            text = re.sub(padrao, lambda m: random_words(m.group()), text)
    return text

jsonl_files = glob.glob("data/events/*.jsonl")
for file in jsonl_files:
    df = pd.read_json(file, lines=True)
    
    for column in df.columns:
        df[column] = df[column].apply(lambda x: apply_obfuscation(x, ofuscation))

    new_file = file.replace("events", "events_processed")
    df.to_json(new_file, orient="records", lines=True, force_ascii=False)