#!/usr/bin/env python3
import unittest
from monitorar_populacao import refs,compare,parse
class PopTests(unittest.TestCase):
    def setUp(self):
        self.rows=refs()
        self.est={y:r["populacao_habitantes"] for y,r in self.rows.items() if r["tipo"]=="estimativa_oficial_ibge_01_julho"}
        self.censo={2022:self.rows[2022]["populacao_habitantes"]}
    def test_sem_diferenca(self):self.assertFalse(any(compare(self.est,self.censo,self.rows).values()))
    def test_novo_ano(self):
        self.est[max(self.rows)+1]=220000
        self.assertEqual(len(compare(self.est,self.censo,self.rows)["novos_anos"]),1)
    def test_lacuna(self):
        self.est[2023]=197277
        self.assertEqual(len(compare(self.est,self.censo,self.rows)["ano_2023_revisar_produto"]),1)
    def test_unidade(self):
        payload=[{"D1C":"Município (Código)","D2C":"Variável (Código)","D3C":"Ano (Código)"},{"D1C":"3302700","D2C":"9324","D3C":"2025","MN":"Pessoas","NC":"6","V":"212470"}]
        self.assertEqual(parse(payload,"9324"),{2025:212470})
        payload[1]["MN"]="Reais"
        with self.assertRaises(ValueError):parse(payload,"9324")
if __name__=="__main__":unittest.main()
