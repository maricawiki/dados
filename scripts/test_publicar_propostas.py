#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from publicar_propostas import collect,DATA,blob,encode
SOURCE="Validar produtores CEMPRE CNAE e leitos CNES (sem publicar)"
class TestProposta(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.dir=self.root/"leitos-proposta"
        self.dir.mkdir()
        name="SAU-002.csv"
        self.raw=(DATA/name).read_bytes().replace(b",223,204,",b",224,204,")
        self.assertNotEqual(self.raw,(DATA/name).read_bytes())
        (self.dir/name).write_bytes(self.raw)
        manifest=json.loads((DATA/"lote-04.manifest.json").read_text())
        manifest["files"][name]=blob(self.raw)
        (self.dir/"lote-04.manifest.json").write_bytes(encode(manifest))
    def test_proposta_alterada(self):
        out=collect(self.root,SOURCE)
        self.assertEqual(set(out),{"SAU-002.csv","lote-04.manifest.json"})
        self.assertEqual(out["SAU-002.csv"],self.raw)
    def test_executavel_rejeitado(self):
        (self.dir/"script.py").write_text("print('x')")
        with self.assertRaises(ValueError):collect(self.root,SOURCE)
    def test_manifesto_adulterado(self):
        m=self.dir/"lote-04.manifest.json"
        obj=json.loads(m.read_text())
        obj["files"]["SAU-002.json"]="0"*40
        m.write_bytes(encode(obj))
        with self.assertRaises(ValueError):collect(self.root,SOURCE)
    def test_fonte_incorreta(self):
        with self.assertRaises(ValueError):collect(self.root,"Monitorar fontes ISP-RJ (sem publicar)")
if __name__=="__main__":unittest.main()
