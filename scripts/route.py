"""Read-only live catalog adapter. No remote code execution or prompt transfer."""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.request import build_opener, HTTPRedirectHandler, Request

ROOT = 'https://api.github.com/repos/tteuw7z/VorteX/git/ref/heads/chatgpt-live'
RAW = 'https://raw.githubusercontent.com/tteuw7z/VorteX/'
LIMIT = 262144
SHA = re.compile(r'[0-9a-f]{40}\Z')

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result

def decode(data):
    if len(data) > LIMIT:
        raise ValueError('Catalog exceeds size limit')
    return json.loads(data, object_pairs_hook=unique, parse_constant=reject_constant)

def reject_constant(_):
    raise ValueError('Non-finite JSON number')

def get(url):
    with build_opener(NoRedirect()).open(Request(url, headers={'User-Agent':'VorteX-Live/1'}), timeout=12) as response:
        return decode(response.read(LIMIT+1))

def text(value, maximum=512):
    return isinstance(value,str) and 0 < len(value) <= maximum and value.isprintable()

def strings(value, maximum=128):
    return (isinstance(value,list) and len(value)<=maximum and all(text(x) for x in value)
            and len(set(value))==len(value))

def validate(obj):
    if not isinstance(obj,dict) or set(obj) != {'schema','source_sha','skills','agents','commands','execution','delivery_authorized'}:
        raise ValueError('Unknown catalog fields')
    if type(obj['schema']) is not int or obj['schema']!=1 or not isinstance(obj['source_sha'],str) or not SHA.fullmatch(obj['source_sha']) or obj['execution']!='host_binding_required' or obj['delivery_authorized'] is not False:
        raise ValueError('Unsupported catalog protocol')
    skills, agents, commands = (obj[k] for k in ('skills','agents','commands'))
    if not all(isinstance(x,list) and 0<len(x)<=512 for x in (skills,agents,commands)):
        raise ValueError('Invalid catalog lists')
    roles=set()
    for row in agents:
        if not isinstance(row,dict) or set(row)!={'role','focus','output'} or not all(text(x) for x in row.values()) or row['role'] in roles:
            raise ValueError('Invalid agent entry')
        roles.add(row['role'])
    names=set()
    for row in skills:
        if not isinstance(row,dict) or set(row)!={'name','keywords','agents','steps'} or not text(row['name'],80) or row['name'] in names or not all(strings(row[k]) for k in ('keywords','agents','steps')) or not set(row['agents'])<=roles:
            raise ValueError('Invalid skill entry')
        names.add(row['name'])
    paths=set()
    for row in commands:
        if not isinstance(row,dict) or set(row)!={'path','arguments'} or not strings(row['path'],8) or not row['path'] or not all(re.fullmatch(r'[A-Za-z0-9_-]+',p) for p in row['path']) or tuple(row['path']) in paths:
            raise ValueError('Invalid command entry')
        paths.add(tuple(row['path']))
        if not isinstance(row['arguments'],list) or len(row['arguments'])>128:
            raise ValueError('Invalid arguments')
        arg_names, flags = set(), set()
        for arg in row['arguments']:
            if not isinstance(arg,dict) or set(arg)!={'name','flags','required'} or not text(arg['name'],128) or not strings(arg['flags'],16) or type(arg['required']) is not bool:
                raise ValueError('Invalid argument entry')
            if arg['name'] in arg_names or flags.intersection(arg['flags']) or not all(re.fullmatch(r'--?[A-Za-z0-9_-]+', f) for f in arg['flags']):
                raise ValueError('Duplicate or malformed argument')
            arg_names.add(arg['name'])
            flags.update(arg['flags'])
    return obj

def sync(fetch=get):
    ref=fetch(ROOT)
    if not isinstance(ref,dict) or not isinstance(ref.get('object'),dict):
        raise ValueError('Invalid channel ref')
    sha=ref['object'].get('sha')
    if ref.get('ref')!='refs/heads/chatgpt-live' or ref['object'].get('type')!='commit' or not isinstance(sha,str) or not SHA.fullmatch(sha):
        raise ValueError('Invalid channel ref')
    return validate(fetch(RAW+sha+'/catalog.json'))

def route(task,catalog,agent_limit=3):
    if not isinstance(task,str) or not task.strip() or len(task)>8192 or type(agent_limit) is not int or not 1<=agent_limit<=4:
        raise ValueError('Nonempty task and agent limit 1–4 required')
    validate(catalog)
    norm=lambda s: ''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c))
    words=re.findall(r'\w+',norm(task))
    tokens=set(words)
    phrase=' '+' '.join(words)+' '
    def score(row):
        matches=set()
        for keyword in row['keywords']:
            parts=re.findall(r'\w+',norm(keyword))
            if len(parts)==1 and parts[0] in tokens:
                matches.add(parts[0])
            elif len(parts)>1 and (' '+' '.join(parts)+' ') in phrase:
                matches.add(' '.join(parts))
        return len(matches)
    ranked=sorted(((score(row), row) for row in catalog['skills']),key=lambda pair:-pair[0])
    chosen=[row for points,row in ranked if points][:3]
    roles=list(dict.fromkeys(r for row in chosen for r in row['agents']))
    if len(roles)>agent_limit:
        roles=list(dict.fromkeys([row['agents'][0] for row in chosen if row['agents']]+roles))[:agent_limit]
    mandatory=[r for r in ('code reviewer','qa','security reviewer') if any(r==a['role'] for a in catalog['agents'])]
    return {'status':'planned','source_sha':catalog['source_sha'],'skills':[r['name'] for r in chosen],'agents':roles,'mandatory_review_roles':mandatory,'fallback':not chosen,'execution':False,'delivery_authorized':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('task',nargs='?'); p.add_argument('--catalog',type=Path); p.add_argument('--agent-limit',type=int,default=3)
    a=p.parse_args()
    try:
        if a.catalog:
            with a.catalog.open('rb') as f: catalog=validate(decode(f.read(LIMIT+1)))
        else: catalog=sync()
        print(json.dumps(route(a.task,catalog,a.agent_limit) if a.task else catalog,ensure_ascii=False))
    except (OSError,ValueError,TypeError,KeyError,RecursionError) as exc:
        print(json.dumps({'status':'unavailable','reason':type(exc).__name__,'execution':False}),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
