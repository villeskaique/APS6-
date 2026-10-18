import unittest
from unittest.mock import patch
from src.usuarios import cadastrar_usuario


class TestCadastroUsuario(unittest.TestCase):
    # Verificar se o cadastro rejeita um CPF com quantidade de caracteres diferente de 11, sem acessar o banco.
    @patch("src.usuarios.conectar")
    def test_cpf_invalido(self, mock_conectar):
        with self.assertRaisesRegex(ValueError, "11 dígitos"):
            cadastrar_usuario(
                cpf="123",
                nome="Usuario Teste",
                nivel_acesso=1,
                caminho_imagem="database/usuario_teste.jpg"
            )

        # Confirmar que a validação ocorreu antes da conexão.
        mock_conectar.assert_not_called()

    # Verificar se um nível de acesso fora dos valores permitidos provoca um erro antes de qualquer operação no banco.
    @patch("src.usuarios.conectar")
    def test_nivel_acesso_invalido(self, mock_conectar):
        with self.assertRaisesRegex(ValueError, "nível de acesso"):
            cadastrar_usuario(
                cpf="12345678901",
                nome="Usuario Teste",
                nivel_acesso=4,
                caminho_imagem="database/usuario_teste.jpg"
            )

        mock_conectar.assert_not_called()

    # Simular um cadastro válido e verificar se a função retorna o identificador gerado pelo banco de dados.
    @patch("src.usuarios.conectar")
    def test_cadastro_valido(self, mock_conectar):
        # Acessar os objetos simulados da conexão e do cursor.
        conexao = mock_conectar.return_value.__enter__.return_value
        cursor = conexao.cursor.return_value.__enter__.return_value

        # Simular o ID retornado após a inserção do usuário.
        cursor.fetchone.return_value = (99,)

        resultado = cadastrar_usuario(
            cpf="98765432100",
            nome="Usuario Teste",
            nivel_acesso=1,
            caminho_imagem="database/usuario_teste.jpg"
        )

        # Confirmar o ID retornado e a execução do cadastro.
        self.assertEqual(resultado, 99)
        cursor.execute.assert_called_once()
        mock_conectar.assert_called_once()

    # Simular uma violação de unicidade para verificar se o erro de CPF duplicado é propagado pela função.
    @patch("src.usuarios.conectar")
    def test_cpf_duplicado(self, mock_conectar):
        import psycopg

        conexao = mock_conectar.return_value.__enter__.return_value
        cursor = conexao.cursor.return_value.__enter__.return_value

        # Simular a exceção lançada pelo banco durante a consulta.
        cursor.execute.side_effect = psycopg.errors.UniqueViolation(
            "CPF duplicado"
        )

        # Confirmar que a exceção esperada não é ocultada.
        with self.assertRaises(psycopg.errors.UniqueViolation):
            cadastrar_usuario(
                cpf="12345678901",
                nome="Usuario Teste",
                nivel_acesso=1,
                caminho_imagem="database/usuario_teste.jpg"
            )

        cursor.execute.assert_called_once()


if __name__ == "__main__":
    # Executar os testes de cadastro diretamente pelo arquivo.
    unittest.main()
