import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.api import app


class TestAPI(unittest.TestCase):
    # Criar um cliente de testes para realizar requisições à API sem precisar iniciar o servidor manualmente.
    def setUp(self):
        self.client = TestClient(app)

    # Verificar se a consulta de dados é recusada quando o usuário não informa um token de autenticação.
    def test_dados_sem_token_retorna_401(self):
        resposta = self.client.get("/dados/1")

        # Confirmar que a API retorna HTTP 401 e a mensagem esperada.
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(
            resposta.json()["detail"],
            "Token de autenticação não informado."
        )

    # Simular uma sessão inexistente para verificar se a API bloqueia o acesso com um token inválido.
    @patch("src.api.obter_sessao", return_value=None)
    def test_sessao_invalida_retorna_401(self, mock_sessao):
        resposta = self.client.get(
            "/dados/1",
            headers={"Authorization": "Bearer token-invalido"}
        )

        # Confirmar a resposta de autenticação e a consulta do token.
        self.assertEqual(resposta.status_code, 401)
        self.assertIn("Sessão inválida", resposta.json()["detail"])
        mock_sessao.assert_called_once_with("token-invalido")

    # Simular um usuário de nível 1 tentando acessar um recurso de nível superior, verificando se o acesso é negado.
    @patch("src.api.consultar_dados")
    @patch("src.api.obter_sessao")
    def test_acesso_negado_retorna_403(
        self, mock_sessao, mock_consultar
    ):
        # Simular uma sessão válida de um usuário de nível 1.
        mock_sessao.return_value = {
            "usuario": "Usuario Teste",
            "nivel_acesso": 1
        }

        # Simular a resposta de acesso negado pelo serviço.
        mock_consultar.return_value = {
            "sucesso": False,
            "mensagem": "Acesso negado.",
            "dados": []
        }

        resposta = self.client.get(
            "/dados/2",
            headers={"Authorization": "Bearer token-teste"}
        )

        # Confirmar que a API retorna HTTP 403.
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.json()["detail"], "Acesso negado.")

    # Simular uma falha na consulta ao banco e verificar se a API retorna um erro de serviço indisponível.
    @patch("src.api.consultar_dados")
    @patch("src.api.obter_sessao")
    def test_falha_banco_retorna_503(
        self, mock_sessao, mock_consultar
    ):
        # Simular uma sessão válida.
        mock_sessao.return_value = {
            "usuario": "Usuario Teste",
            "nivel_acesso": 1
        }

        # Simular a falha controlada retornada pelo serviço.
        mock_consultar.return_value = {
            "sucesso": False,
            "mensagem": "Não foi possível consultar os dados no momento.",
            "dados": []
        }

        resposta = self.client.get(
            "/dados/1",
            headers={"Authorization": "Bearer token-teste"}
        )

        # Confirmar o código HTTP 503 e a mensagem de erro.
        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(
            resposta.json()["detail"],
            "Não foi possível consultar os dados no momento."
        )

    # Simular um estado de reconhecimento com usuário autenticado e verificar se o endpoint /status retorna essas informações.
    @patch("src.api.buscar_usuario_por_id")
    @patch("src.api.obter_sessao")
    def test_status_retorna_estado(self, mock_sessao, mock_usuario):
        mock_sessao.return_value = {"id_usuario": 99}
        mock_usuario.return_value = (
            99,
            "98765432100",
            "Usuario Teste",
            1,
            b"\xff\xd8\xff" + b"\x00" * 10
        )

        resposta = self.client.get(
            "/status",
            headers={"Authorization": "Bearer token-teste"}
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["usuario"], "Usuario Teste")
        self.assertEqual(resposta.json()["cpf"], "98765432100")
        self.assertEqual(resposta.json()["tipo_imagem"], "image/jpeg")

    @patch("src.api.obter_sessao")
    def test_status_sem_usuario_autenticado(self, mock_sessao):
        mock_sessao.return_value = None

        resposta = self.client.get(
            "/status",
            headers={"Authorization": "Bearer token-teste"}
        )

        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(
            resposta.json()["detail"],
            "Sessão inválida ou expirada. Autentique-se novamente."
        )


    # Simular um usuário autenticado pela câmera e verificar se uma nova sessão é criada com os dados corretos.
    @patch("src.api.criar_sessao", return_value="token-teste")
    @patch("src.api.obter_estado")
    def test_iniciar_sessao_com_usuario_autenticado(
        self, mock_estado, mock_criar_sessao
    ):
        mock_estado.return_value = {
            "autenticado": True,
            "id_usuario": 99,
            "usuario": "Usuario Teste",
            "nivel_acesso": 2
        }

        resposta = self.client.post("/sessao")

        # Conferir o retorno da API e os dados da sessão criada.
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["sucesso"])
        self.assertEqual(resposta.json()["token"], "token-teste")
        self.assertEqual(resposta.json()["tipo"], "Bearer")
        self.assertEqual(resposta.json()["nivel_acesso"], 2)

        # Confirmar que a sessão recebeu o usuário e seu nível de acesso.
        mock_criar_sessao.assert_called_once_with(
            id_usuario=99,
            usuario="Usuario Teste",
            nivel_acesso=2
        )

    # Verificar se a API impede a criação de uma sessão quando não há usuário autenticado pela câmera.
    @patch("src.api.criar_sessao")
    @patch("src.api.obter_estado")
    def test_iniciar_sessao_sem_usuario_retorna_401(
        self, mock_estado, mock_criar_sessao
    ):
        mock_estado.return_value = {
            "autenticado": False,
            "usuario": None,
            "nivel_acesso": None
        }

        resposta = self.client.post("/sessao")

        # Confirmar a resposta de erro e que nenhuma sessão foi criada.
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(
            resposta.json()["detail"],
            "Nenhum usuário reconhecido recentemente pela câmera."
        )
        mock_criar_sessao.assert_not_called()

    # Verificar se uma sessão pode ser encerrada utilizando o token enviado no cabeçalho da requisição.
    @patch("src.api.encerrar_sessao")
    def test_finalizar_sessao_com_token(self, mock_encerrar):
        resposta = self.client.delete(
            "/sessao",
            headers={"Authorization": "Bearer token-teste"}
        )

        # Confirmar a resposta e o encerramento com o token informado.
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["sucesso"])
        self.assertEqual(
            resposta.json()["mensagem"],
            "Sessão encerrada."
        )
        mock_encerrar.assert_called_once_with("token-teste")

    # Simular uma consulta autorizada e verificar se os dados retornados pelo serviço são enviados corretamente pela API.
    @patch("src.api.consultar_dados")
    @patch("src.api.obter_sessao")
    def test_consulta_autorizada_retorna_dados(
        self, mock_sessao, mock_consultar
    ):
        mock_sessao.return_value = {
            "usuario": "Usuario Teste",
            "nivel_acesso": 2
        }

        # Simular o resultado de uma consulta autorizada.
        mock_consultar.return_value = {
            "sucesso": True,
            "mensagem": "Acesso autorizado.",
            "usuario": "Usuario Teste",
            "nivel_acesso": 2,
            "nivel_recurso": 2,
            "dados": ["Temperatura: 25 graus"]
        }

        resposta = self.client.get(
            "/dados/2",
            headers={"Authorization": "Bearer token-teste"}
        )

        # Validar o código de sucesso e os dados recebidos.
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["sucesso"])
        self.assertEqual(
            resposta.json()["dados"],
            ["Temperatura: 25 graus"]
        )

        # Confirmar que a sessão foi consultada com o token correto.
        mock_sessao.assert_called_once_with("token-teste")

        # Confirmar os argumentos enviados ao serviço de consulta.
        mock_consultar.assert_called_once_with(
            nome="Usuario Teste",
            nivel_usuario=2,
            nivel_recurso=2
        )

    # Simular um erro genérico na consulta e verificar se a API o transforma em uma resposta HTTP 400.
    @patch("src.api.consultar_dados")
    @patch("src.api.obter_sessao")
    def test_erro_generico_retorna_400(
        self, mock_sessao, mock_consultar
    ):
        mock_sessao.return_value = {
            "usuario": "Usuario Teste",
            "nivel_acesso": 2
        }

        mock_consultar.return_value = {
            "sucesso": False,
            "mensagem": "Erro genérico de consulta.",
            "dados": []
        }

        resposta = self.client.get(
            "/dados/2",
            headers={"Authorization": "Bearer token-teste"}
        )

        # Confirmar o código HTTP e a mensagem de erro retornada.
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(
            resposta.json()["detail"],
            "Erro genérico de consulta."
        )


if __name__ == "__main__":
    # Executar os testes quando o arquivo for iniciado diretamente.
    unittest.main()
