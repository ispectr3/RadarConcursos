from scraping import is_study_or_article, is_generic_page


class TestIsStudyOrArticle:
    def test_study_indicators_in_title(self):
        assert is_study_or_article("Como estudar para concurso", "como-estudar") is True
        assert is_study_or_article("Guia completo de concursos", "guia-completo") is True
        assert is_study_or_article("Resumo para concurso", "resumo-para") is True
        assert is_study_or_article("Edital do Concurso XYZ", "edital-xyz") is False

    def test_para_concursos_without_contest_indicators(self):
        assert is_study_or_article("Matematica para concursos", "matematica") is True

    def test_para_concursos_with_contest_indicators(self):
        assert is_study_or_article("Edital para concursos SP", "edital-sp") is False
        assert is_study_or_article("Vagas para concursos", "vagas-abertas") is False

    def test_non_study_content(self):
        assert is_study_or_article("Concurso Publico SP 2026", "concurso-sp") is False
        assert is_study_or_article(
            "Prefeitura abre edital com 100 vagas", "prefeitura-edital"
        ) is False

    def test_empty_values(self):
        assert is_study_or_article("", "") is False


class TestIsGenericPage:
    def test_known_generic_pages(self):
        assert is_generic_page("concursos-abertos") is True
        assert is_generic_page("lp") is True
        assert is_generic_page("como-estudar") is True
        assert is_generic_page("artigos") is True

    def test_state_pages(self):
        assert is_generic_page("concursos-sp") is True
        assert is_generic_page("concursos-rj") is True
        assert is_generic_page("concursos-mg") is True

    def test_region_pages(self):
        assert is_generic_page("concursos-sudeste") is True
        assert is_generic_page("concursos-nordeste") is True
        assert is_generic_page("concursos-policiais") is True

    def test_non_generic_pages(self):
        assert is_generic_page("edital-prefeitura-sp-2026") is False
        assert is_generic_page("concurso-abc-123") is False
        assert is_generic_page("") is False
