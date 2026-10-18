import unittest
from src.banco_dados import conectar


class TestConexao(unittest.TestCase):

    # Verificar se a conexão real com o banco de dados funciona e se ela aponta para o banco esperado pelo projeto.
    def test_conectar_banco(self):
        # Abrir a conexão e criar um cursor para executar SQL.
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                # Consultar o nome do banco atualmente conectado.
                cursor.execute("SELECT current_database()")
                banco = cursor.fetchone()[0]

        # Confirmar que a conexão utilizou o banco correto.
        self.assertEqual(banco, "aps_reconhecimento_facial")


if __name__ == "__main__":
    # Executar o teste de conexão diretamente pelo arquivo.
    unittest.main()
