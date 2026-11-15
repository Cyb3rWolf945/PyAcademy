# Testes da comparação (pura, sem sandbox): texto, numeros, exato, funções e língua do output esperado.
import compare as c


def test_texto_normaliza_espacos_maiusculas_e_acentos():
    assert c.compare_output("texto", "Vai a andar\n", "  vai   a ANDAR  \n\n\n")
    assert c.compare_output("texto", "Olá, não", "ola,  NAO")
    assert not c.compare_output("texto", "a\nb", "a b")
    assert not c.compare_output("texto", "a\n\nb", "a\nb")


def test_numeros_14_14_0_e_14_virgula_0():
    for actual in ("14", "14.0", "14,0", "O resultado é 14,00 euros", "14.004"):
        assert c.compare_output("numeros", "14", actual), actual
    assert not c.compare_output("numeros", "14", "14.5")
    assert c.compare_output("numeros", "-3 2.5e2", "-3.0\n250")
    assert not c.compare_output("numeros", "1 2", "1")  # número de valores diferente
    assert c.compare_output("numeros", "1000000", "1000000.5")  # tolerância relativa 1e-6


def test_exato_so_tira_uma_quebra_final():
    assert c.compare_output("exato", "ab\n", "ab")
    assert not c.compare_output("exato", "ab", "ab\n\n")
    assert not c.compare_output("exato", "Ab", "ab")
    assert not c.compare_output("exato", "a  b", "a b")


def test_valores_ints_floats_e_tolerancia():
    assert c.values_equal(20, 20.0)
    assert c.values_equal(1.5, 1.5000000001)
    assert not c.values_equal(1, True)
    assert c.values_equal([1, [2, 3]], [1, (2, 3)])
    assert c.values_equal({"a": 1}, {"a": 1.0})
    assert not c.values_equal([1, 2], [1, 2, 3])
    assert c.values_equal(None, None)


def test_ordem_importa_false_compara_como_multiconjunto():
    assert c.values_equal([3, 1, 2, 2], [2, 1, 2, 3], ordered=False)
    assert not c.values_equal([3, 1, 2, 2], [2, 1, 3, 3], ordered=False)
    assert not c.values_equal([1, 2], [2, 1], ordered=True)
    assert c.values_equal([["b", 1], ["a", 2]], [["a", 2], ["b", 1]], ordered=False)


def test_output_localizado():
    exp = {"pt": "Corre!", "en": "Run!"}
    assert c.pick(exp, "pt-PT") == "Corre!" and c.pick(exp, "en") == "Run!"
    assert c.pick("14", "en") == "14"
