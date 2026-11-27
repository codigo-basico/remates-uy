import json, re, pathlib, urllib.request, urllib.parse, datetime
from html.parser import HTMLParser

ROOT = 'https://www.impo.com.uy/remates'
class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip+=1
        if tag=='a':
            href=dict(attrs).get('href','')
            if href: self.links.append(href)
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'RematesUY/1.0 (public auction index)'})
    with urllib.request.urlopen(req,timeout=30) as response:
        p=Parser(); p.feed(response.read().decode(response.headers.get_content_charset() or 'utf-8',errors='replace')); return p
def links(p,base):
    return {urllib.parse.urljoin(base,x) for x in p.links if re.search(r'/bases/avisos-remate/\d+-\d{4}',x)}
path=pathlib.Path('data/remates.json')
old={x['url']:x for x in json.loads(path.read_text())}
urls=links(fetch(ROOT),ROOT)
if not urls: raise RuntimeError('IMPO no devolvió enlaces a edictos; se conservan los datos anteriores')
for url in sorted(urls):
    try:
        p=fetch(url); detail=' '.join(p.parts)
        if len(detail)<150: continue
        low=detail.lower()
        tipo='Vehículos' if re.search(r'\b(veh[ií]culo|autom[oó]vil|camioneta|chasis|motocicleta)',low) else 'Inmuebles' if re.search(r'\b(inmueble|apartamento|terreno|solar)',low) else 'Otros'
        base='Sin base' if re.search(r'\bsin base\b',low) else 'Con base' if re.search(r'\bcon base\b',low) else 'No informado'
        old[url]={'titulo':tipo+' — '+url.rsplit('/',1)[-1],'tipo':tipo,'fecha':None,'departamento':None,'base_estado':base,'base':None,'detalle':detail,'fuente':'IMPO','url':url}
    except Exception as e: print(url,e)
path.write_text(json.dumps(list(old.values()),ensure_ascii=False,indent=2)+'\n')
