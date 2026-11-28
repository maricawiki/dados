#!/usr/bin/env python3
import unittest
from produzir_vitais import reference,propose,serialize,DATA
class VitalTests(unittest.TestCase):
    def test_reproducao(self):
        _,_,v=reference()
        self.assertEqual(propose(v),{})
    def test_revisao(self):
        _,_,v=reference()
        n,d=v[2024]
        self.assertEqual(set(propose({2024:(n+1,d)})),{"SAU-004.csv","SAU-004.json","SAU-005.csv","SAU-005.json","lote-04.manifest.json"})
    def test_nao_preliminar(self):
        with self.assertRaises(ValueError):propose({2025:(2000,20)})
    def test_censo_dependente(self):
        _,_,v=reference()
        n,d=v[2022]
        with self.assertRaises(ValueError):propose({2022:(n+1,d)})
if __name__=="__main__":unittest.main()
