"""Testes com textos SINTÉTICOS (nenhum texto de prova real é versionado — ADR-013)."""
from concurso.features import comando_tipo, formato_alternativas, question_features
from concurso.parse_fcc import join_lines, parse_gabarito
from concurso.pdftext import is_noise


def test_join_lines_hifenizacao():
    assert join_lines(["o le-", "gislador"]) == "o legislador"
    assert join_lines(["aos Estados-", "-membros"]) == "aos Estados-membros"
    assert join_lines(["Lei n o 8.666/1993,", "pelo critério"]) == "Lei n o 8.666/1993, pelo critério"
    assert join_lines(["auto-", "Organização"]) == "auto- Organização"   # maiúscula: não junta


def test_ruido_marca_dagua_e_rodape():
    assert is_noise("pcimarkpci QUJDREVGR0g=:SElKS0w=")
    assert is_noise("www.pciconcursos.com.br")
    assert is_noise("8 SEFAZ-AFRE-Adm.Tributária-CG 1 -P1-S01")
    assert is_noise("PMSLA-ACI-Abrangência Geral-A01-CE 13")
    assert not is_noise("Direito Administrativo")
    assert not is_noise("TCE-PI determinou a abertura de processo de tomada de contas especial contra o gestor.")


def test_gabarito_pares_com_blocos_e_rotulos():
    linhas = [
        "C. Gerais - P1", "Cargo ou opção S01 - AUDITOR", "Tipo gabarito 1",
        "001 - C 002 - A", "003 - E",
        "C. Específicos - P2", "Cargo ou opção S01 - AUDITOR", "Tipo gabarito 1",
        "001 - D 002 - B 003 - A",
    ]
    b = parse_gabarito(linhas)
    assert [(x.cargo, x.tipo, len(x.answers)) for x in b] == [("S01", 1, 3), ("S01", 1, 3)]
    assert b[0].label.startswith("C. Gerais") and b[1].label.startswith("C. Específicos")
    assert b[1].answers[1] == "D"


def test_gabarito_em_grade():
    linhas = ["Número do caderno B02 - ANALISTA", "Tipo gabarito", "2",
              "001 011", "- D - B", "002 012", "- A - E"]
    b = parse_gabarito(linhas)
    assert b[0].cargo == "B02" and b[0].tipo == 2
    assert b[0].answers == {1: "D", 11: "B", 2: "A", 12: "E"}


def test_comando_e_formato():
    alts_combo = {"A": "I e II, apenas.", "B": "I e III, apenas.", "C": "II, apenas.", "D": "III, apenas.", "E": "I, II e III."}
    assert formato_alternativas(alts_combo) == "assertivas_combinadas"
    assert comando_tipo("Considere: I. x. II. y. III. z. Está correto o que se afirma em", alts_combo) == "assertivas_combinadas"
    alts = {k: "texto qualquer da alternativa." for k in "ABCDE"}
    assert comando_tipo("Sobre o tema, assinale a alternativa INCORRETA.", alts) == "assinale_incorreta"
    assert comando_tipo("Em decorrência do fato narrado, o Município", alts) == "completar_frase"


def test_features_basicas():
    alts = {"A": "sempre deverá anular o ato.", "B": "pode convalidar o ato.", "C": "x.", "D": "y.", "E": "z."}
    f = {(a, n): (v, t) for a, n, v, t in question_features(
        "Considere a seguinte situação hipotética: Marta, servidora de determinado Município, praticou ato. O ato",
        None, alts, "B")}
    assert f[("", "cenario_marcador_forte")][0] == 1
    assert f[("", "menciona_determinado")][0] == 1
    assert f[("A", "tem_absoluto")][0] == 1
    assert f[("", "posicao_correta")][1] == "B"
    assert f[("", "correta_e_mais_longa")][0] == 0       # A é a mais longa
