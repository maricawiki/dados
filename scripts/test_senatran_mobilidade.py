import unittest
from unittest.mock import patch
from produzir_senatran import DATA
from senatran_mobilidade import validate_local,reconcile
import json
class MobilityTests(unittest.TestCase):
    def test_base(self):validate_local(DATA)
    def test_reconciliacao(self):
        r=json.loads((DATA/"MOB-004-historico.json").read_text())["serie"][-1]
        labels=[{"tipo_oficial":k,"valor":v} for k,v in r["tipos"].items()]
        with patch("senatran_mobilidade.parse",return_value=labels):
            reconcile(DATA,r["ano"],r["total"],r["fonte_sha256"],b"")
        with patch("senatran_mobilidade.parse",return_value=labels[:-1]):
            with self.assertRaises(ValueError):reconcile(DATA,r["ano"],r["total"],r["fonte_sha256"],b"")
    def test_novo_ano_bloqueado(self):
        with self.assertRaisesRegex(ValueError,"Novo exercício"):reconcile(DATA,2100,100000,"0"*64,b"")
    def test_revisao_bloqueada(self):
        r=json.loads((DATA/"MOB-004-historico.json").read_text())["serie"][-1]
        with self.assertRaisesRegex(ValueError,"Revisão da fonte"):reconcile(DATA,r["ano"],r["total"]+1,r["fonte_sha256"],b"")
if __name__=="__main__":unittest.main()
