import unittest
from unittest.mock import patch
from src import sessoes


class TestSessoes(unittest.TestCase):

    # Limpar as sessões antes de cada teste.
    def setUp(self):
        sessoes.invalidar_sessoes()

    # Limpar as sessões ao terminar cada teste.
    def tearDown(self):
        sessoes.invalidar_sessoes()

    # Verificar a criação de uma sessão.
    @patch("src.sessoes.time", return_value=1000)
    @patch("src.sessoes.token_urlsafe", return_value="token-teste")
    def test_criar_sessao(self, mock_token, mock_time):
        token = sessoes.criar_sessao(99, "Usuario Teste", 2)

        self.assertEqual(token, "token-teste")
        sessao = sessoes.obter_sessao(token)

        self.assertEqual(sessao["id_usuario"], 99)
        self.assertEqual(sessao["usuario"], "Usuario Teste")
        self.assertEqual(sessao["nivel_acesso"], 2)
        self.assertEqual(sessao["criada_em"], 1000)

    # Verificar se um token inexistente retorna None.
    @patch("src.sessoes.time", return_value=1000)
    def test_token_invalido_retorna_none(self, mock_time):
        self.assertIsNone(sessoes.obter_sessao("token-inexistente"))

    # Verificar o encerramento de uma sessão.
    @patch("src.sessoes.time", return_value=1000)
    def test_encerrar_sessao_invalida_token(self, mock_time):
        token = sessoes.criar_sessao(99, "Usuario Teste", 1)

        resultado = sessoes.encerrar_sessao(token)

        self.assertTrue(resultado)
        self.assertIsNone(sessoes.obter_sessao(token))

    # Verificar expiração por inatividade.
    @patch("src.sessoes.time")
    def test_expira_por_inatividade(self, mock_time):
        mock_time.return_value = 1000
        token = sessoes.criar_sessao(99, "Usuario Teste", 1)

        mock_time.return_value = 1000 + sessoes.TEMPO_EXPIRACAO + 1

        self.assertIsNone(sessoes.obter_sessao(token))

    # Verificar expiração pela duração máxima.
    @patch("src.sessoes.time")
    def test_expira_apos_duracao_maxima(self, mock_time):
        mock_time.return_value = 1000
        token = sessoes.criar_sessao(99, "Usuario Teste", 1)

        mock_time.return_value = 1000 + sessoes.TEMPO_MAXIMO_SESSAO + 1

        self.assertIsNone(sessoes.obter_sessao(token))

    # Verificar se a atividade renova o prazo de inatividade.
    @patch("src.sessoes.time")
    def test_atividade_renova_inatividade(self, mock_time):
        mock_time.return_value = 1000
        token = sessoes.criar_sessao(99, "Usuario Teste", 1)

        mock_time.return_value = 1000 + 600
        self.assertIsNotNone(sessoes.obter_sessao(token))

        mock_time.return_value = (
            1000 + 600 + sessoes.TEMPO_EXPIRACAO - 1
        )
        self.assertIsNotNone(sessoes.obter_sessao(token))

    # Verificar se todas as sessões são invalidadas.
    @patch("src.sessoes.time", return_value=1000)
    def test_invalidar_todas_sessoes(self, mock_time):
        token1 = sessoes.criar_sessao(1, "Usuario 1", 1)
        token2 = sessoes.criar_sessao(2, "Usuario 2", 2)

        sessoes.invalidar_sessoes()

        self.assertIsNone(sessoes.obter_sessao(token1))
        self.assertIsNone(sessoes.obter_sessao(token2))

    # Verificar se criar uma sessão remove sessões expiradas.
    @patch(
        "src.sessoes.token_urlsafe",
        side_effect=["token-antigo", "token-novo"]
    )
    @patch("src.sessoes.time")
    def test_criar_sessao_remove_sessoes_expiradas(
        self, mock_time, mock_token
    ):
        mock_time.return_value = 1000
        token_antigo = sessoes.criar_sessao(
            1, "Usuario Antigo", 1
        )

        mock_time.return_value = 1000 + sessoes.TEMPO_EXPIRACAO + 1
        token_novo = sessoes.criar_sessao(
            2, "Usuario Novo", 2
        )

        self.assertEqual(token_antigo, "token-antigo")
        self.assertEqual(token_novo, "token-novo")

        self.assertIsNone(sessoes.obter_sessao(token_antigo))
        self.assertIsNotNone(sessoes.obter_sessao(token_novo))


if __name__ == "__main__":
    unittest.main()
