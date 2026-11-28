import csv
import io
import unittest
import zipfile
from monitorar_anatel import NAME,SERVICES,reference,parse,compare

def pack(rows):
    out=io.StringIO()
    w=csv.writer(out,delimiter=";")
    w.writerow(["Ano","Mês","Acessos","Serviço","Código IBGE","Município","UF"])
    w.writerows(rows)
    blob=io.BytesIO()
    with zipfile.ZipFile(blob,"w") as z:z.writestr(NAME,out.getvalue())
    return blob.getvalue()

class AnatelTests(unittest.TestCase):
    def setUp(self):
        self.base=reference()
        self.rows=[(y,m,n,s,"3302700","Maricá","RJ") for s,series in self.base.items() for (y,m),n in series.items()]
    def test_reproduzir(self):
        result=compare(parse(pack(self.rows)),self.base)
        self.assertTrue(all(not any(v[k] for k in ("ausentes","revisoes","novos_dezembros")) for v in result.values()))
    def test_novembro_nao_anual(self):
        service=SERVICES["TEL-001"]
        y=max(self.base[service])[0]+1
        result=compare(parse(pack(self.rows+[(y,11,123,service,"3302700","Maricá","RJ")])),self.base)
        self.assertEqual(result[service]["novos_dezembros"],[])
    def test_dezembro_novo(self):
        service=SERVICES["TEL-001"]
        y=max(self.base[service])[0]+1
        result=compare(parse(pack(self.rows+[(y,12,123,service,"3302700","Maricá","RJ")])),self.base)
        self.assertEqual(result[service]["novos_dezembros"],[{"ano":y,"acessos":123}])
    def test_duplicidade(self):
        with self.assertRaises(ValueError):parse(pack(self.rows+[self.rows[0]]))
    def test_revisao(self):
        row=list(self.rows[0]);row[2]+=1
        result=compare(parse(pack([row]+self.rows[1:])),self.base)
        self.assertEqual(len(result[row[3]]["revisoes"]),1)
if __name__=="__main__":unittest.main()
