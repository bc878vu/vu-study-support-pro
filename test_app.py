import unittest, tempfile, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
class TestApp(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();app.DB=Path(cls.tmp.name)/'test.sqlite3';app.init_db()
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_seed(self):
  data=app.public_data();self.assertTrue(data['services']);self.assertEqual(data['settings']['whatsapp'],'923098851445')
 def test_validation(self):
  valid=app.validate('services',{'title':'Tutor','description':'Guidance','icon':'book','sort_order':2,'active':1});self.assertEqual(valid['title'],'Tutor')
  with self.assertRaises(ValueError):app.validate('services',{'title':'','description':'x'})
  with self.assertRaises(ValueError):app.validate('faqs',{'question':'Q','answer':'A','active':5})
 def test_static_assets_resolve_from_repository_root(self):
  from unittest.mock import Mock
  for url,expected_type in [('/static/site.css','text/css'),('/static/site.js','text/javascript'),('/static/admin.js','text/javascript'),('/','text/html'),('/admin','text/html')]:
   fake=Mock()
   app.Handler.static(fake,url)
   fake.send.assert_called_once()
   args=fake.send.call_args.args
   self.assertEqual(args[0],200)
   self.assertGreater(len(args[1]),0)
   self.assertEqual(args[2],expected_type)
 def test_static_unknown_path_returns_404(self):
  from unittest.mock import Mock
  fake=Mock()
  app.Handler.static(fake,'/static/unknown.js')
  fake.error.assert_called_once_with(404,'Not found')
 def test_password_requires_secret(self):
  old=app.ADMIN_PASSWORD;app.ADMIN_PASSWORD='';self.assertFalse(app.password_ok('anything'));app.ADMIN_PASSWORD=old
if __name__=='__main__':unittest.main()
