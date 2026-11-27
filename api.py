import json,re,pathlib,urllib.request,urllib.parse,datetime,unicodedata
from html.parser import HTMLParser
ROOT='https://www.impo.com.uy/remates'
ANV='https://www.anv.gub.uy/remates'
DEPS='Artigas|Canelones|Cerro Largo|Colonia|Durazno|Flores|Florida|Lavalleja|Maldonado|Montevideo|Paysandú|Río Negro|Rivera|Rocha|Salto|San José|Soriano|Tacuarembó|Treinta y Tres'
class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.links=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.skip+=1
        if tag=='a': self.links.append(dict(attrs).get('href',''))
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip(): self.parts.append(data.strip())
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 RematesUY'}),timeout=40) as r:
        p=Parser(); p.feed(r.read().decode(r.headers.get_content_charset() or 'utf-8',errors='replace')); return p
def field(s,pattern):
    m=re.search(pattern,s,re.I|re.S); return m.group(1).strip() if m else ''
def clean(s): return ' '.join(s.split())
def iso(s):
    try: return datetime.datetime.strptime(s,'%d/%m/%Y').date().isoformat()
    except ValueError: return None
def impo():
    p=fetch(ROOT); raw='\n'.join(p.parts); dep=None; rows=[]
    tokens=re.split(r'(?im)(^\s*(?:'+DEPS+r')\s*$|Fecha\s*:\s*\d{1,2}/\d{1,2}/\d{4})',raw)
    i=1
    while i<len(tokens)-1:
        head,body=tokens[i].strip(),tokens[i+1]; i+=2
        if re.fullmatch(DEPS,head,re.I): dep=head.title(); continue
        date=iso(field(head,r'Fecha\s*:\s*(\S+)'))
        if not date: continue
        ref=re.search(r'aviso\s+(\d+)/0?(\d{2,4})',body,re.I)
        if not ref: continue
        year=int(ref[2]); year=2000+year if year<100 else year
        url=f'https://www.impo.com.uy/bases/avisos-remate/{ref[1]}-{year}'
        desc=clean(field(body,r'Bien\s+a\s+rematar\s*[-:]\s*(.*?)(?=Condiciones\s*[-:]|Rematador\s*[-:]|Publicado en|$)'))
        if not desc: continue
        conditions=clean(field(body,r'Condiciones\s*[-:]\s*(.*?)(?=Rematador\s*[-:]|Publicado en|$)'))
        place=clean(field(body,r'Lugar\s*:\s*(.*?)(?=Bien\s+a\s+rematar|$)'))
        auctioneer=clean(field(body,r'Rematador\s*[-:]\s*(.*?)(?=Publicado en|$)'))
        cats=[]
        if re.search(r'veh[ií]culo|autom[oó]vil|camioneta|motocicleta|chasis',desc,re.I): cats.append('Vehículos')
        if re.search(r'inmueble|terreno|solar|apartamento|propiedad horizontal|fracci[oó]n de campo',desc,re.I): cats.append('Inmuebles')
        if not cats: cats=['Otros']
        base='Sin base' if re.search(r'sin base',conditions,re.I) else 'Con base' if re.search(r'\bbase\b|tasaci[oó]n',conditions,re.I) else 'No informado'
        for cat in cats:
            rows.append(dict(titulo=desc[:160],tipo=cat,fecha=date,hora=field(body,r'Hora\s*:\s*(\d{1,2}:\d{2})'),departamento=dep,base_estado=base,base=conditions or None,detalle=desc+' | Lugar: '+place+' | Rematador: '+auctioneer,fuente='IMPO',url=url))
    if not rows: raise RuntimeError('No se reconocieron avisos IMPO')
    return rows
def anv():
    p=fetch(ANV); raw=' '.join(p.parts); rows=[]
    months='enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
    for m in re.finditer(r'Remates del ([\d, y]+) de ('+'|'.join(months)+r') de (\d{4})\s*[-–]\s*(Montevideo|Interior)',raw,re.I):
        for day in re.findall(r'\d+',m[1]):
            date=datetime.date(int(m[3]),months.index(m[2].lower())+1,int(day)).isoformat()
            rows.append(dict(titulo='Agenda de remates ANV — '+m[4],tipo='Inmuebles',fecha=date,departamento='Montevideo' if m[4]=='Montevideo' else None,base_estado='Con base',base=None,detalle='Agenda agrupada: consultar nómina y edictos para identificar cada inmueble, precio y horario.',fuente='ANV',url=ANV))
    if not rows: raise RuntimeError('No se reconoció agenda ANV')
    return rows

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from concurrent.futures import ThreadPoolExecutor
app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=['https://codigo-basico.github.io'],allow_methods=['GET'],allow_headers=['*'])
@app.get('/')
def health(): return {'status':'ok'}
@app.get('/buscar')
def buscar():
    def run(item):
        name,fn=item
        try: return name,fn(),None
        except Exception as e: return name,[],str(e)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,[('IMPO',impo),('ANV',anv)]))
    return {'registros':[row for _,rows,_ in results for row in rows],'fuentes':[{'nombre':name,'ok':error is None,'cantidad':len(rows),'error':error} for name,rows,error in results],'consultado':datetime.datetime.now(datetime.timezone.utc).isoformat()}
