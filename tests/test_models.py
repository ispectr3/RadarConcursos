from models import Edital


def test_edital_minimal():
    e = Edital(titulo="teste", url="https://example.com", fonte="test")
    assert e.titulo == "teste"
    assert e.organizacao is None


def test_edital_full():
    e = Edital(
        titulo="Concurso XYZ",
        url="https://example.com/xyz",
        fonte="test",
        organizacao="Org",
        cargo="Analista",
        salario="R$ 10.000",
        estado="SP",
        inscricoes="01/01 a 01/02",
        data_prova="15/02",
        vagas="10",
        resumo="Resumo do concurso",
    )
    assert e.organizacao == "Org"
    assert e.salario == "R$ 10.000"


def test_to_json_dict():
    e = Edital(titulo="teste", url="https://ex.com", fonte="test")
    d = e.to_json_dict()
    assert d["titulo"] == "teste"
    assert d["fonte"] == "test"
    assert "extra" in d
    assert d["extra"] == {}
