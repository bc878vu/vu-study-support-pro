"""VU Study Support — dependency-free Python/SQLite application."""
import os, json, sqlite3, secrets, hashlib, hmac, time, re, threading
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from http.cookies import SimpleCookie

ROOT=Path(__file__).resolve().parent
DB=Path(os.getenv('DATABASE_PATH', str(ROOT/'data.sqlite3')))
HOST=os.getenv('HOST','127.0.0.1'); PORT=int(os.getenv('PORT','8000'))
ADMIN_USER=os.getenv('ADMIN_USER','admin')
ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD','')
SECURE_COOKIES=os.getenv('SECURE_COOKIES','0')=='1'
MAX_BODY=64*1024
SESSIONS={}; LOCK=threading.RLock()
TABLES={'services':('title','description','icon','sort_order','active'), 'packages':('title','description','price','features','sort_order','active'), 'faqs':('question','answer','sort_order','active'), 'testimonials':('name','quote','sort_order','active')}
DEFAULTS={
 'services':[
 ('Semester Planning','Structured study plans for working and busy VU students.','calendar',1,1),('Assignment Guidance','Understand requirements, concepts and solution approaches.','file',2,1),('Quiz Preparation','Practice questions and topic-wise revision support.','check',3,1),('GDB Guidance','Research, discussion structure and academic writing guidance.','message',4,1),('Final Year Project','Project planning, documentation and technical mentoring.','code',5,1),('Exam Preparation','Midterm and final exam preparation with past papers.','book',6,1)],
 'packages':[
 ('Starter','Focused support for specific subjects or academic tasks.','Contact for quote','Study planning\nPractice resources\nWhatsApp guidance',1,1),('Semester Plus','Ongoing guidance throughout your semester.','Contact for quote','Semester roadmap\nExam preparation\nAssignment guidance',2,1),('Project Mentorship','Personalized final year project guidance.','Contact for quote','Project planning\nTechnical mentoring\nDocumentation review',3,1)],
 'faqs':[
 ('Do you support working students?','Yes. Flexible study planning is available for students managing jobs and studies.',1,1),('Can I choose individual services?','Yes. Contact us for a tailored support package.',2,1),('Do you guarantee grades?','No. Academic results depend on individual learning and university assessment.',3,1)],
 'testimonials':[]
}

def conn():
 c=sqlite3.connect(DB,timeout=10); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA journal_mode=WAL'); return c

def init_db():
 DB.parent.mkdir(parents=True,exist_ok=True)
 with conn() as c:
  for table, fields in TABLES.items():
   cols=', '.join(f'{f} '+('INTEGER NOT NULL DEFAULT 1' if f in ('sort_order','active') else 'TEXT NOT NULL') for f in fields)
   c.execute(f'CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})')
   if c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0 and DEFAULTS[table]:
    placeholders=','.join('?' for _ in fields)
    c.executemany(f'INSERT INTO {table} ({",".join(fields)}) VALUES ({placeholders})',DEFAULTS[table])
  c.execute('CREATE TABLE IF NOT EXISTS inquiries (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL, subject TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT "new", created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
  c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
  for k,v in {'brand':'VU Study Support','hero_title':'Make every semester count.','hero_subtitle':'Personalized academic guidance for ambitious Virtual University students and busy professionals.','whatsapp':'923098851445','email':'','announcement':'Admissions support & study planning inquiries are open.'}.items():
   c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)',(k,v))

def password_ok(candidate):
 # ADMIN_PASSWORD_HASH format: salt_hex:pbkdf2_hex (recommended for production)
 stored=os.getenv('ADMIN_PASSWORD_HASH','')
 if stored:
  try:
   salt, expected=stored.split(':',1)
   actual=hashlib.pbkdf2_hmac('sha256',candidate.encode(),bytes.fromhex(salt),310000).hex()
   return hmac.compare_digest(actual,expected)
  except (ValueError,TypeError): return False
 return bool(ADMIN_PASSWORD) and hmac.compare_digest(candidate,ADMIN_PASSWORD)

def public_data():
 with conn() as c:
  return {'settings':{r['key']:r['value'] for r in c.execute('SELECT * FROM settings')},**{t:[dict(r) for r in c.execute(f'SELECT * FROM {t} WHERE active=1 ORDER BY sort_order,id')] for t in TABLES}}

def validate(table,obj):
 if table not in TABLES or not isinstance(obj,dict): raise ValueError('Invalid resource')
 result={}
 for field in TABLES[table]:
  if field in ('sort_order','active'):
   try: v=int(obj.get(field,1))
   except (ValueError,TypeError): raise ValueError(f'Invalid {field}')
   if field=='active' and v not in (0,1): raise ValueError('Invalid active')
   if field=='sort_order' and not 0<=v<=9999: raise ValueError('Invalid order')
  else:
   v=obj.get(field,'')
   if not isinstance(v,str) or len(v)>1500: raise ValueError(f'Invalid {field}')
   v=v.strip()
   if not v and field not in ('icon','price','features'): raise ValueError(f'{field} is required')
  result[field]=v
 return result

class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args): pass
 def send(self,status=200,data=None,content_type='application/json',extra=None):
  payload=(json.dumps(data,ensure_ascii=False).encode() if content_type=='application/json' else data)
  self.send_response(status);self.send_header('Content-Type',content_type+'; charset=utf-8');self.send_header('Content-Length',str(len(payload)))
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.send_header('X-Frame-Options','DENY');self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'")
  self.send_header('Cache-Control','no-store' if self.path.startswith('/api/') else 'public, max-age=300')
  for k,v in (extra or {}).items(): self.send_header(k,v)
  self.end_headers();self.wfile.write(payload)
 def error(self,status,msg): self.send(status,{'error':msg})
 def body(self):
  n=int(self.headers.get('Content-Length','0'))
  if n<1 or n>MAX_BODY: raise ValueError('Invalid request size')
  try: return json.loads(self.rfile.read(n))
  except (json.JSONDecodeError,UnicodeDecodeError): raise ValueError('Invalid JSON')
 def session(self):
  cookie=SimpleCookie()
  try: cookie.load(self.headers.get('Cookie',''))
  except Exception: return None
  token=cookie.get('vu_session')
  if not token:return None
  with LOCK:
   session=SESSIONS.get(token.value)
   if session and session['expires']>time.time():return session
   SESSIONS.pop(token.value,None)
  return None
 def protected(self):
  s=self.session()
  if not s: self.error(401,'Sign in required');return False
  if self.command in ('POST','PUT','DELETE') and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),s['csrf']): self.error(403,'Invalid CSRF token');return False
  return True
 def static(self,path):
  files={'/':'index.html','/admin':'admin.html','/static/site.css':'site.css','/static/site.js':'site.js','/static/admin.js':'admin.js'}
  if path not in files: return self.error(404,'Not found')
  file=ROOT/files[path];mime='text/css' if file.suffix=='.css' else 'text/javascript' if file.suffix=='.js' else 'text/html'
  self.send(200,file.read_bytes(),mime)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/api/public':return self.send(data=public_data())
  if p=='/api/health':return self.send(data={'status':'ok'})
  if p=='/api/admin/session':
   s=self.session();return self.send(data={'authenticated':bool(s),'csrf':s['csrf'] if s else None})
  if p.startswith('/api/admin/'):
   if not self.protected():return
   resource=p.split('/')[-1]
   with conn() as c:
    if resource in TABLES:return self.send(data=[dict(r) for r in c.execute(f'SELECT * FROM {resource} ORDER BY sort_order,id')])
    if resource=='inquiries':return self.send(data=[dict(r) for r in c.execute('SELECT * FROM inquiries ORDER BY id DESC LIMIT 500')])
    if resource=='settings':return self.send(data={r['key']:r['value'] for r in c.execute('SELECT * FROM settings')})
   return self.error(404,'Not found')
  return self.static(p)
 def do_POST(self):
  p=urlparse(self.path).path
  try:
   obj=self.body()
   if p=='/api/inquiries':
    if not isinstance(obj,dict):raise ValueError('Invalid inquiry')
    name=str(obj.get('name','')).strip();phone=str(obj.get('phone','')).strip();subject=str(obj.get('subject','')).strip();msg=str(obj.get('message','')).strip()
    if not 2<=len(name)<=80 or not re.fullmatch(r'[+\d ()-]{9,22}',phone) or not 2<=len(subject)<=100 or not 5<=len(msg)<=1500:raise ValueError('Please complete all fields correctly')
    if obj.get('website'):return self.send(201,{'success':True}) # honeypot
    with conn() as c:c.execute('INSERT INTO inquiries(name,phone,subject,message) VALUES (?,?,?,?)',(name,phone,subject,msg))
    return self.send(201,{'success':True})
   if p=='/api/admin/login':
    if not isinstance(obj,dict):raise ValueError('Invalid login')
    if not hmac.compare_digest(str(obj.get('username','')),ADMIN_USER) or not password_ok(str(obj.get('password',''))):return self.error(401,'Invalid credentials')
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
    with LOCK:SESSIONS[token]={'csrf':csrf,'expires':time.time()+8*3600}
    cookie=f'vu_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+('; Secure' if SECURE_COOKIES else '')
    return self.send(200,{'success':True,'csrf':csrf},extra={'Set-Cookie':cookie})
   if not p.startswith('/api/admin/') or not self.protected():return
   if p=='/api/admin/logout':
    ck=SimpleCookie();ck.load(self.headers.get('Cookie',''));token=ck.get('vu_session')
    if token:
     with LOCK:SESSIONS.pop(token.value,None)
    return self.send(200,{'success':True},extra={'Set-Cookie':'vu_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
   table=p.split('/')[-1];vals=validate(table,obj)
   with conn() as c:
    fields=list(vals);q=','.join('?' for _ in fields)
    cur=c.execute(f'INSERT INTO {table} ({",".join(fields)}) VALUES ({q})',tuple(vals.values()))
    return self.send(201,{'id':cur.lastrowid})
  except ValueError as e:return self.error(400,str(e))
 def do_PUT(self):
  p=urlparse(self.path).path
  if not self.protected():return
  try:
   obj=self.body();parts=p.split('/')
   if p=='/api/admin/settings':
    if not isinstance(obj,dict):raise ValueError('Invalid settings')
    allowed={'brand','hero_title','hero_subtitle','whatsapp','email','announcement'}
    if set(obj)-allowed:raise ValueError('Unknown setting')
    if any(not isinstance(v,str) or len(v)>500 for v in obj.values()):raise ValueError('Invalid value')
    with conn() as c:
     for k,v in obj.items():c.execute('UPDATE settings SET value=? WHERE key=?',(v.strip(),k))
    return self.send(data={'success':True})
   if len(parts)==5 and parts[3] in TABLES and parts[4].isdigit():
    table=parts[3];values=validate(table,obj);ident=int(parts[4]);fields=list(values)
    with conn() as c:
     cur=c.execute(f'UPDATE {table} SET '+','.join(f'{f}=?' for f in fields)+' WHERE id=?',(*values.values(),ident))
     return self.send(200 if cur.rowcount else 404,{'success':bool(cur.rowcount)})
   if len(parts)==5 and parts[3]=='inquiries' and parts[4].isdigit():
    if not isinstance(obj,dict) or obj.get('status') not in ('new','contacted','closed'):raise ValueError('Invalid status')
    with conn() as c:
     cur=c.execute('UPDATE inquiries SET status=? WHERE id=?',(obj['status'],int(parts[4])))
     return self.send(200 if cur.rowcount else 404,{'success':bool(cur.rowcount)})
   return self.error(404,'Not found')
  except ValueError as e:return self.error(400,str(e))
 def do_DELETE(self):
  p=urlparse(self.path).path
  if not self.protected():return
  parts=p.split('/')
  if len(parts)!=5 or not parts[4].isdigit() or parts[3] not in (*TABLES,'inquiries'):return self.error(404,'Not found')
  with conn() as c:
   cur=c.execute(f'DELETE FROM {parts[3]} WHERE id=?',(int(parts[4]),))
   return self.send(200 if cur.rowcount else 404,{'success':bool(cur.rowcount)})

if __name__=='__main__':
 init_db()
 print(f'VU Study Support running at http://{HOST}:{PORT} (admin: /admin)')
 ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
