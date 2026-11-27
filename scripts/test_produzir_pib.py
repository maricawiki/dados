#!/usr/bin/env python3
import csv
import unittest
from produzir_pib import DATA,parse,propose,serialize
class PIBTests(unittest.TestCase):
    def setUp(self):
        with (DATA/"ECO-001.csv").open(encoding="utf-8",newline="") as f:self.values={int(x["ano"]):int(x["pib_mil_reais"]) for x in csv.DictReader(f)}
    def fixture(self):
        return [{"D1C":"Município (Código)","D2C":"Variável (Código)","D3C":"Ano (Código)"}]+[{"D1C":"3302700","D2C":"37","D3C":str(y),"NC":"6","MN":"Mil Reais","V":str(v)} for y,v in self.values.items()]
    def test_reproducao(self):
        self.assertEqual(parse(self.fixture()),self.values)
        self.assertEqual(serialize(self.values),(DATA/"ECO-001.csv").read_bytes())
        self.assertEqual(propose(self.values),{})
    def test_unidade(self):
        data=self.fixture()
        data[1]["MN"]="Reais"
        with self.assertRaises(ValueError):parse(data)
    def test_lacuna(self):
        data=self.fixture()
        del data[2]
        with self.assertRaises(ValueError):parse(data)
    def test_percapita(self):
        v=dict(self.values)
        v[2023]+=1
        with self.assertRaises(ValueError):propose(v)
    def test_revisao_historica(self):
        v=dict(self.values)
        v[2002]+=1
        self.assertEqual(set(propose(v)),{"ECO-001.csv","ECO-001.json","lote-03.manifest.json"})
if __name__=="__main__":unittest.main()
