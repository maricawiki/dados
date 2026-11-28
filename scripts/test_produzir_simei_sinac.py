import unittest
from produzir_simei_sinac import reference,propose
class ReceitaTests(unittest.TestCase):
    def test_reproducao(self):self.assertEqual(propose({}),{})
    def test_revisao(self):
        row=dict(reference()["ECO-008"]["serie"][-1]);row["valor"]+=1
        self.assertEqual(set(propose({"ECO-008":[row]})),{"ECO-008.csv","ECO-008.json","ECO-009.csv","ECO-009.json","lote-03.manifest.json"})
    def test_inclusao(self):
        row=dict(reference()["ECO-010"]["serie"][-1]);row["valor"]=1
        with self.assertRaises(ValueError):propose({"ECO-010":[row]})
    def test_sem_novo_exercicio(self):
        row=dict(reference()["ECO-008"]["serie"][-1]);row["ano"]=2026
        with self.assertRaises(ValueError):propose({"ECO-008":[row]})
if __name__=="__main__":unittest.main()
