#!/usr/bin/env python3
"""60 표시칸을 넘는 EBM/XML 한국어 문장을 로컬 모델로 축약한다."""

import argparse, hashlib, html, json, re, time, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from text_layout import visible_units

ATTR = re.compile(r'''(?P<head>\s(?:Text|text)\s*=\s*)(?P<q>["'])(?P<value>.*?)(?P=q)''', re.DOTALL)
CTRL = re.compile(r"<(?:[A-Za-z][A-Za-z0-9_]*|#[0-9A-Fa-f]+)>")
COLOR = re.compile(r"<#[0-9A-Fa-f]+>")
HEADER = 32

def selection_units(text): return len(re.sub(r"<[A-Za-z][A-Za-z0-9_]*>", "X", text.replace("<CR>", "")))
def units(text): return visible_units(COLOR.sub("", text.replace("<CR>", "")))
def controls(text): return [x for x in CTRL.findall(text) if x != "<CR>"]

def call(base, model, items):
    system = '''한국어 게임 문장을 의미와 말투를 유지하면서 최대 60자 이내로 간결하게 축약한다.
공백과 문장부호도 1자로 센다. <CR>은 삭제해도 되지만 다른 <IM00>, <RG> 같은 제어 코드는 철자·개수·순서를 반드시 유지한다.
문장을 자르거나 미완성 어미로 끝내지 않는다. {"translations":[{"id":"입력 id","translation":"축약문"}]} JSON만 출력한다.'''
    body={"model":model,"temperature":0.1,"max_tokens":4096,"messages":[{"role":"system","content":system},{"role":"user","content":json.dumps(items,ensure_ascii=False)}]}
    req=urllib.request.Request(base.rstrip('/')+'/chat/completions',data=json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=900) as r: out=json.loads(r.read().decode())
    content=out['choices'][0]['message']['content'].strip()
    content=re.sub(r'^```(?:json)?\s*|\s*```$','',content,flags=re.I)
    parsed=json.JSONDecoder().raw_decode(content)[0]; rows=parsed.get('translations',parsed) if isinstance(parsed,dict) else parsed
    return {str(x['id']):str(x['translation']) for x in rows}

def parse_ebm(data,path):
    count=int.from_bytes(data[:4],'little');pos=4;rows=[]
    for i in range(count):
        ln=int.from_bytes(data[pos+HEADER:pos+HEADER+4],'little');start=pos+HEADER+4;end=start+ln
        payload=data[start:end]
        if not payload.endswith(b'\0'): raise ValueError(f'{path}:{i}')
        rows.append((data[pos:pos+HEADER],payload[:-1].decode('utf-8')));pos=end
    if pos!=len(data): raise ValueError(f'{path}:trailing')
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--base-url',default='http://127.0.0.1:1234/v1');ap.add_argument('--model',default='gemma-4-26b-a4b-it-qat');ap.add_argument('--batch-size',type=int,default=4);a=ap.parse_args()
    root=a.repo/'translations'; occurrences=[]
    for p in sorted((root/'romfs/Event/event').rglob('*.ebm')):
        rows=parse_ebm(p.read_bytes(),p)
        for i,(_,t) in enumerate(rows):
            if selection_units(t)>60: occurrences.append(('ebm',p,i,t))
    # 독립 UI XML은 각자 고유한 레이아웃을 사용하므로 대화창 3줄 제한을 적용하지 않는다.
    for p in sorted((root/'romfs/Saves/systemMessage').rglob('*.xml')):
        try: raw=p.read_text(encoding='utf-8'); ET.fromstring(raw)
        except Exception: continue
        for i,m in enumerate(ATTR.finditer(raw)):
            t=html.unescape(m.group('value'))
            if selection_units(t)>60: occurrences.append(('xml',p,i,t))
    unique=list(dict.fromkeys(x[3] for x in occurrences))
    # 후보 순서가 바뀌어도 다른 문장의 캐시를 재사용하지 않도록 원문 해시를 키로 쓴다.
    ids={t:'sha256:'+hashlib.sha256(t.encode('utf-8')).hexdigest() for t in unique}
    cache_path=a.repo/'build/three_line_shortening_cache.json';cache=json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    reviewed = {
        "PlayStation<RG>Vita 소프트웨어, 세르노사쥬에서 만든 아이템을 아르노사쥬로 전송합니다. 전송할 수 있는 것은 각종 아이템 각 1개뿐입니다.":
        "PlayStation<RG>Vita판 세르노사쥬 아이템을 아르노사쥬로 전송합니다. 아이템별 1개만 가능합니다.",
    }
    for source, shortened in reviewed.items():
        if source in ids:
            cache[ids[source]] = shortened
    for t in unique:
        if t.startswith("아이우에오카키") and not controls(t):
            cache[ids[t]] = t[:60]
        if not any('가' <= c <= '힣' for c in t):
            cache[ids[t]] = t
    pending=[t for t in unique if ids[t] not in cache]
    for start in range(0,len(pending),a.batch_size):
        batch=pending[start:start+a.batch_size]; items=[{'id':ids[t],'source':t.replace('<CR>','')} for t in batch]
        try: result=call(a.base_url,a.model,items)
        except Exception: result={}
        for t in batch:
            rid=ids[t]; v=result.get(rid)
            if v is None or units(v)>60 or controls(v)!=controls(t):
                v=None
                for _ in range(3):
                    try:
                        one=call(a.base_url,a.model,[{'id':rid,'source':t.replace('<CR>',''),'requirement':'반드시 60자 이하'}]);v=one.get(rid)
                        if v is not None and units(v)<=60 and controls(v)==controls(t): break
                    except Exception: pass
            if v is None or units(v)>60 or controls(v)!=controls(t): raise ValueError(f'invalid shortening {rid}: {v}')
            cache[rid]=v
        cache_path.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8');print(f'{min(start+len(batch),len(pending))}/{len(pending)}',flush=True)
    repl={t:cache[ids[t]] for t in unique}
    for p in sorted((root/'romfs/Event/event').rglob('*.ebm')):
        rows=parse_ebm(p.read_bytes(),p);out=bytearray(len(rows).to_bytes(4,'little'))
        for h,t in rows:
            v=repl.get(t,t);payload=v.encode()+b'\0';out+=h+len(payload).to_bytes(4,'little')+payload
        p.write_bytes(out)
    for p in sorted((root/'romfs/Saves/systemMessage').rglob('*.xml')):
        try: raw=p.read_text(encoding='utf-8')
        except Exception: continue
        def sub(m):
            t=html.unescape(m.group('value'));v=repl.get(t,t);esc=html.escape(v,quote=True)
            return m.group('head')+m.group('q')+esc+m.group('q')
        p.write_text(ATTR.sub(sub,raw),encoding='utf-8',newline='')
    print(json.dumps({'occurrences':len(occurrences),'unique':len(unique)},ensure_ascii=False))
if __name__=='__main__':main()
