from models import Edital
from formatter import esc, get_saudacao, format_telegram_message


class TestEsc:
    def test_none(self):
        assert esc(None) == "Não informado"

    def test_empty_string(self):
        assert esc("") == "Não informado"

    def test_html_escaping(self):
        assert "<" not in esc("<script>")
        assert "&lt;" in esc("<b>texto</b>")

    def test_normal_text(self):
        assert esc("Analista") == "Analista"


class TestGetSaudacao:
    def test_returns_string(self):
        s = get_saudacao()
        assert isinstance(s, str)
        assert len(s) > 0


class TestFormatTelegramMessage:
    def test_minimal_edital(self):
        e = Edital(titulo="teste", url="https://ex.com", fonte="test")
        msg = format_telegram_message(e)
        assert "teste" in msg
        assert "RADAR CONCURSOS" in msg
        assert "Não informado" in msg

    def test_full_edital(self):
        e = Edital(
            titulo="Concurso XYZ",
            url="https://ex.com/xyz",
            fonte="test",
            organizacao="Org",
            cargo="Analista",
            salario="R$ 10.000",
            estado="SP",
            vagas="10",
            inscricoes="01/01 a 01/02",
            isencao="Nao ha",
            data_prova="15/02/2026",
            resumo="Um resumo do concurso",
        )
        msg = format_telegram_message(e)
        assert "Org" in msg
        assert "Analista" in msg
        assert "SP" in msg
        assert "R$ 10.000" in msg
        assert "10" in msg
        assert "01/01 a 01/02" in msg
        assert "Um resumo do concurso" in msg
