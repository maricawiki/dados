#!/usr/bin/env python3
"""Regressões determinísticas sem acesso externo; não certificam disponibilidade gov.br."""
import io
import unittest
import zipfile
from unittest.mock import patch
from urllib.error import URLError
import produzir_senatran as s

class SenatranTests(unittest.TestCase):
    def test_incremental(self):
        rows=s.load_validated_fleet()
        last=rows[-1]
        year=int(last["ano"])
        new={**last,"ano":str(year+1),"frota":last["frota"]+1}
        with patch.object(s,"LAST_FULL_YEAR",year+1), patch.object(s,"read_official_file",return_value=last) as direct, patch.object(s,"official_december",return_value=new) as discover:
            self.assertEqual(s.fetch_fleet(),rows+[new])
            direct.assert_called_once_with(year,last["pagina"],last["arquivo"])
            discover.assert_called_once_with(year+1)
    def test_historico_explicitamente_solicitado(self):
        rows=s.load_validated_fleet()
        with patch.object(s,"LAST_FULL_YEAR",int(rows[-1]["ano"])),patch.object(s,"official_december",side_effect=rows) as full:
            self.assertEqual(s.fetch_fleet(full=True),rows)
            self.assertEqual(full.call_count,len(rows))
    def test_falha_fonte_nao_retorna_cache_como_atualizado(self):
        before=s.FROTA.read_bytes()
        with patch.object(s,"read_official_file",side_effect=URLError("simulacao")),patch.object(s,"official_december") as discover:
            with self.assertRaises(URLError):s.fetch_fleet()
            discover.assert_not_called()
        self.assertEqual(s.FROTA.read_bytes(),before)
    def make_xlsx(self,year,total):
        ns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        shared=f'<sst xmlns="{ns}"><si><t>Frota de veículos DEZ/{year}</t></si><si><t>RJ</t></si><si><t>Maricá</t></si></sst>'
        sheet=f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row><row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2" t="s"><v>2</v></c><c r="C2"><v>{total}</v></c><c r="D2"><v>40000</v></c><c r="E2"><v>10000</v></c></row></sheetData></worksheet>'
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            z.writestr("xl/sharedStrings.xml",shared)
            z.writestr("xl/worksheets/sheet1.xml",sheet)
        return out.getvalue()
    def test_planilha_dezembro_e_soma(self):
        self.assertEqual(s.parse_xlsx(self.make_xlsx(2025,50000),2025)[0],50000)
        with self.assertRaises(ValueError):s.parse_xlsx(self.make_xlsx(2024,50000),2025)
        with self.assertRaises(ValueError):s.parse_xlsx(self.make_xlsx(2025,49999),2025)
    def test_fonte_nao_oficial_bloqueada(self):
        with self.assertRaises(ValueError):s.download("http://www.gov.br/arquivo",10000,"*/*")
        with self.assertRaises(ValueError):s.download("https://example.com/arquivo",10000,"*/*")

if __name__=="__main__":
    unittest.main()
