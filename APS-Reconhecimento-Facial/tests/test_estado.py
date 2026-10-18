import unittest
from unittest import TestCase
from unittest.mock import patch
from src.estado import (
    atualizar_estado,
    obter_estado,
    estado_reconhecimento,
)


class TestEstado(TestCase):

    # Guardar o estado original antes de cada teste e começar com os dados de reconhecimento limpos.
    def setUp(self):
        self.estado_original = estado_reconhecimento.copy()
        atualizar_estado()

    # Restaurar os dados originais depois de cada teste, evitando interferência entre os casos testados.
    def tearDown(self):
        estado_reconhecimento.update(self.estado_original)

    # Verificar se a função atualiza corretamente os dados e registra o horário informado pelo mock.
    @patch("src.estado.time", return_value=100)
    def test_atualizar_estado(self, mock_time):
        atualizar_estado(
            autenticado=True,
            usuario="Usuario Teste",
            nivel_acesso=2,
            distancia=0.45,
        )

        # Conferir os valores armazenados no estado global.
        self.assertTrue(estado_reconhecimento["autenticado"])
        self.assertEqual(estado_reconhecimento["usuario"], "Usuario Teste")
        self.assertEqual(estado_reconhecimento["nivel_acesso"], 2)
        self.assertEqual(estado_reconhecimento["distancia"], 0.45)
        self.assertEqual(estado_reconhecimento["atualizado_em"], 100)

    # Verificar se um estado recente é retornado sem perder as informações de autenticação.
    @patch("src.estado.time", return_value=101)
    def test_obter_estado_atualizado(self, mock_time):
        atualizar_estado(
            autenticado=True,
            usuario="Usuario Teste",
            nivel_acesso=2,
            distancia=0.45,
        )

        estado = obter_estado()

        # Confirmar os dados e verificar que o horário interno não faz parte do resultado público.
        self.assertTrue(estado["autenticado"])
        self.assertEqual(estado["usuario"], "Usuario Teste")
        self.assertEqual(estado["nivel_acesso"], 2)
        self.assertEqual(estado["distancia"], 0.45)
        self.assertNotIn("atualizado_em", estado)

    # Simular a passagem de quatro segundos e verificar se o estado de autenticação expira após o limite de três.
    @patch("src.estado.time", side_effect=[100, 104])
    def test_expira_estado_apos_tres_segundos(self, mock_time):
        atualizar_estado(
            autenticado=True,
            usuario="Usuario Teste",
            nivel_acesso=2,
            distancia=0.45,
        )

        estado = obter_estado()

        # Confirmar que os dados de autenticação foram removidos.
        self.assertFalse(estado["autenticado"])
        self.assertIsNone(estado["usuario"])
        self.assertEqual(estado["nivel_acesso"], 0)
        self.assertIsNone(estado["distancia"])

    # Verificar se o estado continua válido quando se passaram exatamente três segundos, conforme a condição de expiração.
    @patch("src.estado.time", side_effect=[100, 103])
    def test_estado_nao_expira_exatamente_em_tres_segundos(self, mock_time):
        atualizar_estado(
            autenticado=True,
            usuario="Usuario Teste",
            nivel_acesso=2,
            distancia=0.45,
        )

        estado = obter_estado()

        # O estado só expira quando a diferença é maior que três.
        self.assertTrue(estado["autenticado"])
        self.assertEqual(estado["usuario"], "Usuario Teste")

    # Verificar se alterar o dicionário retornado por obter_estado() não modifica diretamente o estado global armazenado.
    def test_obter_estado_retorna_copia(self):
        atualizar_estado(
            autenticado=True,
            usuario="Usuario Teste",
            nivel_acesso=2,
            distancia=0.45,
        )

        with patch("src.estado.time", return_value=101):
            estado = obter_estado()

        # Alterar a cópia retornada pela função.
        estado["usuario"] = "Outro Usuario"

        # Confirmar que o estado original permanece inalterado.
        self.assertEqual(
            estado_reconhecimento["usuario"],
            "Usuario Teste",
        )


if __name__ == "__main__":
    # Executar os testes de estado diretamente pelo arquivo.
    unittest.main()
