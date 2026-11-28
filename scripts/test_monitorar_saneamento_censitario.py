import unittest
from monitorar_saneamento_censitario import baseline,parse
class SanTests(unittest.TestCase):
    def test_cobertura(self):self.assertEqual(len(baseline()),7)
    def test_parse(self):
        p=[{"D1C":"Município (Código)","D2C":"Variável (Código)","D3C":"Ano (Código)","D4C":"Categoria (Código)"},{"D1C":"3302700","D2C":"381","D3C":"2022","D4C":"72129","NC":"6","MN":"Domicílios","V":"73454"}]
        self.assertEqual(parse(p,2022,"381","1821"),{"72129":73454})
        p[1]["D1C"]="3303302"
        with self.assertRaises(ValueError):parse(p,2022,"381","1821")
if __name__=="__main__":unittest.main()
