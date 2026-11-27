#!/usr/bin/env python3
import io
import json
import unittest
from produzir_caged_mov import DATA,parse_rows,quarters,verify_existing,month_after,build,remote_path
class MovTests(unittest.TestCase):
    def setUp(self):
        self.m=json.loads((DATA/"TRB-001.json").read_text())
        self.q=json.loads((DATA/"TRB-002.json").read_text())
    def test_cache(self):verify_existing(self.m,self.q)
    def test_parser(self):
        text="municipio;saldomovimentacao;competenciamov\n330270;1;202610\n330270;-1;202610\n330000;1;202610\n"
        self.assertEqual(parse_rows(io.StringIO(text),"2026-10")["saldo"],0)
        with self.assertRaises(ValueError):parse_rows(io.StringIO(text),"2026-11")
    def test_mes_novo_sem_trimestre_parcial(self):
        last=self.m["serie"][-1]["competencia"]
        nxt=month_after(last)
        n=len(self.q["serie"])
        data=build(self.m,self.q,[({"competencia":nxt,"admissoes":1200,"desligamentos":1100,"saldo":100},
          {"competencia":nxt,"ftp":remote_path(nxt),"sha256":"a"*64})])
        self.assertEqual(len(self.q["serie"]),len(self.m["serie"])//3)
        self.assertEqual(set(data),{"TRB-001.csv","TRB-001.json","TRB-002.csv","TRB-002.json"})
        self.assertEqual(json.loads(data["TRB-001.json"])["serie"][-1]["competencia"],nxt)
    def test_virada(self):self.assertEqual(month_after("2026-12"),"2027-01")
if __name__=="__main__":unittest.main()
