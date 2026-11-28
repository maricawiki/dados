#!/usr/bin/env python3
import unittest
from copy import deepcopy
from monitorar_inep_distorcao import baseline,compare,KEYS,NETWORKS
from inep_distorcao_fonte import number
class TDI(unittest.TestCase):
    def test_cobertura(self):
        data=baseline()
        self.assertEqual(sorted(data),list(range(2016,2026)))
        for d in data.values():
            self.assertEqual(set(d["redes"]),set(NETWORKS))
            for r in d["redes"].values():self.assertEqual(set(r),set(KEYS))
    def test_lacuna(self):
        self.assertIsNone(number("--"))
        self.assertEqual(number(0),0)
    def test_revisao(self):
        v=baseline()[2025]
        compare(v,v)
        r=deepcopy(v)
        r["redes"]["Total"][KEYS[0]]=99
        with self.assertRaises(ValueError):compare(r,v)
if __name__=="__main__":unittest.main()
